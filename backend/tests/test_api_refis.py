"""Testes do endpoint de troca de refis e de sua serialização transacional."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from src.api.dependencias import get_agora, get_session
from src.entities import Armadilha, Refil
from src.repositories.armadilha_repository import ArmadilhaRepository
from src.repositories.refil_repository import RefilRepository

_AGORA = datetime(2026, 3, 21, tzinfo=timezone.utc)
_AMBIENTE_FICTICIO = {
    "DATABASE_URL": "postgresql://db-ficticio:5432/armadilhas",
    "MODEL_WEIGHTS_PATH": "/caminho-ficticio/pesos.pt",
    "MODEL_VERSION": "v0.1.0-dev",
    "UPLOADS_DIR": "/diretorio-ficticio/uploads",
    "CORS_ORIGENS": "http://localhost:5173",
}


@pytest.fixture
def client(session: Session, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Cria a API com a sessão transacional e o instante fixo do teste."""
    for nome, valor in _AMBIENTE_FICTICIO.items():
        monkeypatch.setenv(nome, valor)
    monkeypatch.setenv("LIMIAR_ATENCAO", "40")
    monkeypatch.setenv("LIMIAR_TROCAR", "70")

    from src.main import create_app

    app = create_app()

    def substituir_sessao() -> Session:
        yield session

    app.dependency_overrides[get_session] = substituir_sessao
    app.dependency_overrides[get_agora] = lambda: _AGORA
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _assert_erro(response, status_code: int, codigo: str) -> dict:
    """Confere o envelope público de erro e retorna seus campos internos."""
    assert response.status_code == status_code
    assert response.headers["content-type"].startswith("application/json")
    corpo = response.json()
    assert set(corpo) == {"erro"}
    assert corpo["erro"]["codigo"] == codigo
    assert "mensagem" in corpo["erro"]
    return corpo["erro"]


def test_trocar_refil_encerra_o_ciclo_e_responde_no_formato_publico(
    client: TestClient,
    session: Session,
) -> None:
    armadilha = ArmadilhaRepository(session).create(identificador="ARM-TROCA-ATIVA")
    anterior = RefilRepository(session).create(
        armadilha_id=armadilha.id,
        data_instalacao=date(2026, 3, 10),
    )

    response = client.post(
        f"/api/armadilhas/{armadilha.id}/refis",
        json={"data_instalacao": "2026-03-21"},
    )

    assert response.status_code == 201
    assert response.headers["content-type"].startswith("application/json")
    corpo = response.json()
    assert set(corpo) == {"refil_encerrado", "refil_novo"}
    assert corpo["refil_encerrado"] == {
        "id": str(anterior.id),
        "data_instalacao": "2026-03-10",
        "data_troca": "2026-03-21",
        "dias_ate_troca": 11,
    }
    assert set(corpo["refil_novo"]) == {"id", "data_instalacao", "dias_em_uso"}
    assert corpo["refil_novo"]["data_instalacao"] == "2026-03-21"
    assert corpo["refil_novo"]["dias_em_uso"] == 0
    refil_ativo = RefilRepository(session).get_active_for_armadilha(armadilha.id)
    assert refil_ativo is not None
    assert str(refil_ativo.id) == corpo["refil_novo"]["id"]


def test_trocar_refil_sem_ciclo_ativo_cria_apenas_o_novo(
    client: TestClient,
    session: Session,
) -> None:
    armadilha = ArmadilhaRepository(session).create(identificador="ARM-SEM-ATIVO")

    response = client.post(
        f"/api/armadilhas/{armadilha.id}/refis",
        json={"data_instalacao": "2026-03-21"},
    )

    assert response.status_code == 201
    assert response.json()["refil_encerrado"] is None
    assert response.json()["refil_novo"]["data_instalacao"] == "2026-03-21"
    assert len(RefilRepository(session).list_closed_for_armadilha(armadilha.id)) == 0


def test_trocar_refil_reverte_o_encerramento_se_a_criacao_falhar(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    armadilha = ArmadilhaRepository(session).create(identificador="ARM-ATOMICA")
    anterior = RefilRepository(session).create(
        armadilha_id=armadilha.id,
        data_instalacao=date(2026, 3, 1),
    )
    session.commit()

    def falhar_criacao(*_args, **_kwargs):
        raise RuntimeError("Falha fictícia na criação do ciclo substituto.")

    monkeypatch.setattr(RefilRepository, "create", falhar_criacao)
    response = client.post(
        f"/api/armadilhas/{armadilha.id}/refis",
        json={"data_instalacao": "2026-03-21"},
    )

    _assert_erro(response, 500, "ERRO_INTERNO")
    repositorio = RefilRepository(session)
    ativo = repositorio.get_active_for_armadilha(armadilha.id)
    assert ativo is not None
    assert ativo.id == anterior.id
    assert ativo.data_troca is None
    assert repositorio.list_closed_for_armadilha(armadilha.id) == []


@pytest.mark.parametrize(
    ("instalacao", "data_refil", "tipo_erro"),
    [
        (date(2026, 3, 20), "2026-03-22", "data_futura"),
        (date(2026, 3, 20), "2026-03-19", "data_anterior"),
    ],
)
def test_trocar_refil_rejeita_datas_incoerentes_sem_alterar_o_ciclo(
    client: TestClient,
    session: Session,
    instalacao: date,
    data_refil: str,
    tipo_erro: str,
) -> None:
    armadilha = ArmadilhaRepository(session).create(
        identificador=f"ARM-DATA-{tipo_erro.upper()}"
    )
    anterior = RefilRepository(session).create(
        armadilha_id=armadilha.id,
        data_instalacao=instalacao,
    )
    session.commit()

    response = client.post(
        f"/api/armadilhas/{armadilha.id}/refis",
        json={"data_instalacao": data_refil},
    )

    erro = _assert_erro(response, 422, "VALIDACAO_FALHOU")
    assert erro["detalhes"] == {"campo": "data_instalacao"}
    assert data_refil not in response.text
    repositorio = RefilRepository(session)
    ativo = repositorio.get_active_for_armadilha(armadilha.id)
    assert ativo is not None
    assert ativo.id == anterior.id
    assert ativo.data_troca is None
    assert repositorio.list_closed_for_armadilha(armadilha.id) == []


def test_trocar_refil_rejeita_armadilha_inexistente(client: TestClient) -> None:
    armadilha_id = uuid4()

    response = client.post(
        f"/api/armadilhas/{armadilha_id}/refis",
        json={"data_instalacao": "2026-03-21"},
    )

    erro = _assert_erro(response, 404, "ARMADILHA_NAO_ENCONTRADA")
    assert erro["detalhes"] == {"armadilha_id": str(armadilha_id)}


def test_trocar_refil_rejeita_uuid_invalido(client: TestClient) -> None:
    response = client.post(
        "/api/armadilhas/nao-e-uuid/refis",
        json={"data_instalacao": "2026-03-21"},
    )

    _assert_erro(response, 422, "VALIDACAO_FALHOU")


@pytest.mark.parametrize(
    ("corpo", "valor_privado"),
    [
        (
            {"data_instalacao": "2026-03-21", "campo_extra": "NAO-REPETIR"},
            "NAO-REPETIR",
        ),
        ({}, ""),
        ({"data_instalacao": "21/03/2026"}, "21/03/2026"),
    ],
)
def test_trocar_refil_rejeita_corpo_com_campo_ausente_ou_invalido(
    client: TestClient,
    corpo: dict,
    valor_privado: str,
) -> None:
    response = client.post(f"/api/armadilhas/{uuid4()}/refis", json=corpo)

    _assert_erro(response, 422, "VALIDACAO_FALHOU")
    if valor_privado:
        assert valor_privado not in response.text


def test_duas_trocas_sequenciais_preservam_dois_ciclos_encerrados(
    client: TestClient,
    session: Session,
) -> None:
    armadilha = ArmadilhaRepository(session).create(identificador="ARM-SEQUENCIAL")
    primeiro = RefilRepository(session).create(
        armadilha_id=armadilha.id,
        data_instalacao=date(2026, 3, 1),
    )

    primeira_resposta = client.post(
        f"/api/armadilhas/{armadilha.id}/refis",
        json={"data_instalacao": "2026-03-20"},
    )
    segunda_resposta = client.post(
        f"/api/armadilhas/{armadilha.id}/refis",
        json={"data_instalacao": "2026-03-21"},
    )

    assert primeira_resposta.status_code == 201
    assert segunda_resposta.status_code == 201
    repositorio = RefilRepository(session)
    encerrados = repositorio.list_closed_for_armadilha(armadilha.id)
    assert len(encerrados) == 2
    assert encerrados[0].id == primeiro.id
    assert [refil.data_troca for refil in encerrados] == [
        date(2026, 3, 20),
        date(2026, 3, 21),
    ]
    assert repositorio.get_active_for_armadilha(armadilha.id).data_instalacao == date(
        2026, 3, 21
    )


def test_openapi_declara_respostas_de_erro_da_troca(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    operacao = response.json()["paths"]["/api/armadilhas/{armadilha_id}/refis"]["post"]
    assert {"201", "404", "422", "500"}.issubset(operacao["responses"])


def test_trocas_concorrentes_em_sessoes_reais_produzem_ciclos_coerentes(
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for nome, valor in _AMBIENTE_FICTICIO.items():
        monkeypatch.setenv(nome, valor)
    monkeypatch.setenv("LIMIAR_ATENCAO", "40")
    monkeypatch.setenv("LIMIAR_TROCAR", "70")

    identificador = f"ARM-CONCORRENTE-{uuid4()}"
    with Session(engine) as sessao_inicial:
        armadilha = ArmadilhaRepository(sessao_inicial).create(
            identificador=identificador
        )
        RefilRepository(sessao_inicial).create(
            armadilha_id=armadilha.id,
            data_instalacao=date(2026, 3, 1),
        )
        sessao_inicial.commit()
        armadilha_id = armadilha.id

    barreira = Barrier(2)

    from src.main import create_app

    apps = [create_app(), create_app()]

    def sessao_por_requisicao():
        with Session(engine, expire_on_commit=False) as sessao:
            barreira.wait(timeout=10)
            yield sessao

    for app in apps:
        app.dependency_overrides[get_session] = sessao_por_requisicao
        app.dependency_overrides[get_agora] = lambda: _AGORA

    def solicitar_troca(indice: int):
        with TestClient(apps[indice]) as test_client:
            return test_client.post(
                f"/api/armadilhas/{armadilha_id}/refis",
                json={"data_instalacao": "2026-03-21"},
            )

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            respostas = list(executor.map(solicitar_troca, range(2)))

        assert [resposta.status_code for resposta in respostas] == [201, 201]
        with Session(engine) as sessao_verificacao:
            repositorio = RefilRepository(sessao_verificacao)
            ativo = repositorio.get_active_for_armadilha(armadilha_id)
            encerrados = repositorio.list_closed_for_armadilha(armadilha_id)
            assert ativo is not None
            assert len(encerrados) == 2
            assert all(
                refil.data_troca is not None
                and refil.data_troca >= refil.data_instalacao
                for refil in encerrados
            )
            assert ativo.data_instalacao == date(2026, 3, 21)
    finally:
        for app in apps:
            app.dependency_overrides.clear()
        with Session(engine) as sessao_limpeza:
            sessao_limpeza.execute(
                delete(Refil).where(Refil.armadilha_id == armadilha_id)
            )
            sessao_limpeza.execute(
                delete(Armadilha).where(Armadilha.id == armadilha_id)
            )
            sessao_limpeza.commit()
