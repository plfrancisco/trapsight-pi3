"""Testes dos endpoints de armadilha com PostgreSQL descartável."""

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event
from sqlalchemy.orm import Session

from src.api.dependencias import get_agora, get_session
from src.entities import StatusAnalise
from src.repositories.analise_repository import AnaliseRepository
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
def client(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    """Cria o app sem abrir conexão e injeta a sessão transacional do teste."""
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


def _adicionar_analise(
    session: Session,
    refil_id,
    analisado_em: datetime,
    percentual: str,
    status: StatusAnalise,
) -> None:
    """Insere uma leitura de teste sem gravar imagem no disco."""
    AnaliseRepository(session).create(
        refil_id=refil_id,
        analisado_em=analisado_em,
        percentual_coberto=Decimal(percentual),
        status=status,
        caminho_imagem="testes/sem-imagem.png",
        modelo_versao="v0.1.0-dev+00000000",
    )


def _assert_erro(response, status_code: int, codigo: str) -> dict:
    """Confere envelope e Content-Type para uma resposta padronizada."""
    assert response.status_code == status_code
    assert response.headers["content-type"].startswith("application/json")
    corpo = response.json()
    assert set(corpo) == {"erro"}
    assert corpo["erro"]["codigo"] == codigo
    assert "mensagem" in corpo["erro"]
    return corpo["erro"]


def test_listar_armadilhas_sem_registros(client: TestClient) -> None:
    response = client.get("/api/armadilhas")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == []


def test_listar_armadilhas_consolida_campos_nulos_estados_e_ordem(
    client: TestClient,
    session: Session,
) -> None:
    repositorio_armadilha = ArmadilhaRepository(session)
    repositorio_armadilha.create(identificador="ARM-Z-SEM-REFIL")
    sem_analises = repositorio_armadilha.create(identificador="ARM-A-SEM-ANALISE")
    refil_sem_analises = RefilRepository(session).create(
        armadilha_id=sem_analises.id,
        data_instalacao=date(2026, 3, 20),
    )
    armadilha_ok = repositorio_armadilha.create(identificador="ARM-OK")
    refil_ok = RefilRepository(session).create(
        armadilha_id=armadilha_ok.id,
        data_instalacao=date(2026, 3, 10),
    )
    _adicionar_analise(
        session,
        refil_ok.id,
        datetime(2026, 3, 10, tzinfo=timezone.utc),
        "20.00",
        StatusAnalise.OK,
    )
    _adicionar_analise(
        session,
        refil_ok.id,
        datetime(2026, 3, 20, tzinfo=timezone.utc),
        "40.00",
        StatusAnalise.OK,
    )
    armadilha_atencao = repositorio_armadilha.create(identificador="ARM-ATENCAO")
    refil_atencao = RefilRepository(session).create(
        armadilha_id=armadilha_atencao.id,
        data_instalacao=date(2026, 3, 10),
    )
    _adicionar_analise(
        session,
        refil_atencao.id,
        datetime(2026, 3, 10, tzinfo=timezone.utc),
        "30.00",
        StatusAnalise.OK,
    )
    _adicionar_analise(
        session,
        refil_atencao.id,
        datetime(2026, 3, 20, tzinfo=timezone.utc),
        "60.00",
        StatusAnalise.ATENCAO,
    )
    armadilha_trocar = repositorio_armadilha.create(identificador="ARM-TROCAR")
    refil_trocar = RefilRepository(session).create(
        armadilha_id=armadilha_trocar.id,
        data_instalacao=date(2026, 3, 1),
    )
    _adicionar_analise(
        session,
        refil_trocar.id,
        datetime(2026, 3, 15, tzinfo=timezone.utc),
        "71.00",
        StatusAnalise.TROCAR,
    )
    _adicionar_analise(
        session,
        refil_trocar.id,
        datetime(2026, 3, 20, tzinfo=timezone.utc),
        "80.00",
        StatusAnalise.TROCAR,
    )

    response = client.get("/api/armadilhas")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    itens = response.json()
    assert [item["identificador"] for item in itens] == [
        "ARM-TROCAR",
        "ARM-ATENCAO",
        "ARM-OK",
        "ARM-A-SEM-ANALISE",
        "ARM-Z-SEM-REFIL",
    ]
    assert itens[0]["status"] == "trocar"
    assert itens[0]["dias_ate_saturar"] == 0
    assert itens[0]["em_alerta_desde"] == "2026-03-15T00:00:00Z"
    assert itens[1]["status"] == "atencao"
    assert itens[1]["dias_ate_saturar"] == 2
    assert itens[1]["percentual_atual"] == 60.0
    assert isinstance(itens[1]["percentual_atual"], float)
    assert itens[1]["ultima_analise_em"] == "2026-03-20T00:00:00Z"
    assert itens[1]["refil_ativo"]["dias_em_uso"] == 11
    assert itens[2]["status"] == "ok"
    assert itens[2]["dias_ate_saturar"] == 14
    assert itens[3]["refil_ativo"]["id"] == str(refil_sem_analises.id)
    assert itens[3]["percentual_atual"] is None
    assert itens[3]["status"] is None
    assert itens[3]["ultima_analise_em"] is None
    assert itens[3]["dias_ate_saturar"] is None
    assert itens[3]["em_alerta_desde"] is None
    assert itens[4]["refil_ativo"] is None
    assert itens[4]["percentual_atual"] is None
    assert itens[4]["status"] is None


@pytest.mark.parametrize("quantidade", [5, 20])
def test_listagem_executa_tres_selects_com_qualquer_quantidade_de_armadilhas(
    client: TestClient,
    session: Session,
    engine: Engine,
    quantidade: int,
) -> None:
    repositorio = ArmadilhaRepository(session)
    for indice in range(quantidade):
        repositorio.create(identificador=f"ARM-{indice:03d}")

    consultas: list[str] = []

    def contar_selects(_conn, _cursor, statement, _parameters, _context, _many) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            consultas.append(statement)

    event.listen(engine, "before_cursor_execute", contar_selects)
    try:
        response = client.get("/api/armadilhas")
    finally:
        event.remove(engine, "before_cursor_execute", contar_selects)

    assert response.status_code == 200
    assert len(consultas) == 3


def test_criar_armadilha_com_e_sem_refil_inicial(
    client: TestClient,
) -> None:
    sem_refil = client.post(
        "/api/armadilhas",
        json={"identificador": "ARM-SEM-REFIL", "modelo": "StickFly"},
    )
    com_refil = client.post(
        "/api/armadilhas",
        json={
            "identificador": "ARM-COM-REFIL",
            "modelo": "StickFly",
            "localizacao": None,
            "data_instalacao": "2026-03-20",
            "criar_refil_inicial": True,
        },
    )

    assert sem_refil.status_code == 201
    assert sem_refil.headers["content-type"].startswith("application/json")
    assert sem_refil.json()["refil_ativo"] is None
    assert sem_refil.json()["refis_anteriores"] == []
    assert sem_refil.json()["modelo"] == "StickFly"
    assert com_refil.status_code == 201
    assert com_refil.headers["content-type"].startswith("application/json")
    assert com_refil.json()["refil_ativo"]["data_instalacao"] == "2026-03-20"
    assert com_refil.json()["refil_ativo"]["dias_em_uso"] == 1


def test_post_exige_data_para_refil_inicial(client: TestClient) -> None:
    response = client.post(
        "/api/armadilhas",
        json={"identificador": "ARM-DATA-OBRIGATORIA", "criar_refil_inicial": True},
    )

    erro = _assert_erro(response, 422, "VALIDACAO_FALHOU")
    assert erro["detalhes"]["campos_invalidos"]


@pytest.mark.parametrize(
    ("corpo", "valor_privado"),
    [
        (
            {"identificador": "ARM-VALIDA", "campo_desconhecido": "NAO-REPETIR"},
            "NAO-REPETIR",
        ),
        ({"identificador": ""}, ""),
        ({"identificador": "X" * 65}, "X" * 65),
    ],
)
def test_post_rejeita_campos_invalidos_sem_repetir_valores_do_cliente(
    client: TestClient,
    corpo: dict,
    valor_privado: str,
) -> None:
    response = client.post("/api/armadilhas", json=corpo)

    erro = _assert_erro(response, 422, "VALIDACAO_FALHOU")
    assert isinstance(erro["detalhes"]["campos_invalidos"], list)
    if valor_privado:
        assert valor_privado not in response.text


def test_post_identificador_duplicado_nao_deixa_armadilha_orfa(
    client: TestClient,
    session: Session,
) -> None:
    ArmadilhaRepository(session).create(identificador="ARM-DUPLICADA")
    session.commit()

    response = client.post(
        "/api/armadilhas",
        json={
            "identificador": "ARM-DUPLICADA",
            "criar_refil_inicial": True,
            "data_instalacao": "2026-03-21",
        },
    )

    erro = _assert_erro(response, 409, "IDENTIFICADOR_DUPLICADO")
    assert erro["detalhes"] == {"identificador": "ARM-DUPLICADA"}
    session.rollback()
    assert [item.identificador for item in ArmadilhaRepository(session).list_all()] == [
        "ARM-DUPLICADA"
    ]


def test_get_detalhe_inclui_historico_e_duracao_dos_refis(
    client: TestClient,
    session: Session,
) -> None:
    armadilha = ArmadilhaRepository(session).create(
        identificador="ARM-HISTORICO",
        modelo="Modelo A",
        localizacao="Recebimento",
        data_instalacao=date(2026, 2, 1),
    )
    repositorio_refil = RefilRepository(session)
    anterior = repositorio_refil.create(
        armadilha_id=armadilha.id,
        data_instalacao=date(2026, 2, 1),
        data_troca=date(2026, 2, 28),
    )
    ativo = repositorio_refil.create(
        armadilha_id=armadilha.id,
        data_instalacao=date(2026, 3, 1),
    )
    _adicionar_analise(
        session,
        ativo.id,
        datetime(2026, 3, 1, tzinfo=timezone.utc),
        "20.00",
        StatusAnalise.OK,
    )
    _adicionar_analise(
        session,
        ativo.id,
        datetime(2026, 3, 11, tzinfo=timezone.utc),
        "50.00",
        StatusAnalise.ATENCAO,
    )

    response = client.get(f"/api/armadilhas/{armadilha.id}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    detalhe = response.json()
    assert detalhe["id"] == str(armadilha.id)
    assert detalhe["refil_ativo"]["id"] == str(ativo.id)
    assert detalhe["refil_ativo"]["dias_em_uso"] == 20
    assert detalhe["refis_anteriores"] == [
        {
            "id": str(anterior.id),
            "data_instalacao": "2026-02-01",
            "data_troca": "2026-02-28",
            "dias_ate_troca": 27,
        }
    ]
    assert detalhe["percentual_atual"] == 50.0
    assert isinstance(detalhe["percentual_atual"], float)
    assert detalhe["status"] == "atencao"


def test_get_nao_encontrada_e_uuid_invalido_usam_erros_padrao(
    client: TestClient,
) -> None:
    ausente = client.get(f"/api/armadilhas/{uuid4()}")
    erro = _assert_erro(ausente, 404, "ARMADILHA_NAO_ENCONTRADA")
    assert erro["detalhes"]["armadilha_id"] in ausente.url.path

    uuid_invalido = client.get("/api/armadilhas/nao-e-uuid")
    _assert_erro(uuid_invalido, 422, "VALIDACAO_FALHOU")


def test_patch_parcial_limpa_valor_e_rejeita_corpo_vazio_e_data(
    client: TestClient,
    session: Session,
) -> None:
    armadilha = ArmadilhaRepository(session).create(
        identificador="ARM-PATCH",
        modelo="Modelo inicial",
        localizacao="Local inicial",
    )
    session.commit()

    parcial = client.patch(
        f"/api/armadilhas/{armadilha.id}",
        json={"localizacao": "Local atualizado"},
    )
    limpar = client.patch(f"/api/armadilhas/{armadilha.id}", json={"modelo": None})
    data_nao_editavel = client.patch(
        f"/api/armadilhas/{armadilha.id}",
        json={"data_instalacao": "2026-03-01"},
    )
    vazio = client.patch(f"/api/armadilhas/{armadilha.id}", json={})
    identificador_nulo = client.patch(
        f"/api/armadilhas/{armadilha.id}",
        json={"identificador": None},
    )

    assert parcial.status_code == 200
    assert parcial.json()["localizacao"] == "Local atualizado"
    assert parcial.json()["modelo"] == "Modelo inicial"
    assert limpar.status_code == 200
    assert limpar.json()["modelo"] is None
    _assert_erro(data_nao_editavel, 422, "VALIDACAO_FALHOU")
    _assert_erro(vazio, 422, "VALIDACAO_FALHOU")
    _assert_erro(identificador_nulo, 422, "VALIDACAO_FALHOU")


def test_patch_duplicado_e_nao_encontrado_usam_erros_padrao(
    client: TestClient,
    session: Session,
) -> None:
    repositorio = ArmadilhaRepository(session)
    original = repositorio.create(identificador="ARM-ORIGINAL")
    alvo = repositorio.create(identificador="ARM-ALVO")
    session.commit()

    duplicado = client.patch(
        f"/api/armadilhas/{alvo.id}",
        json={"identificador": "ARM-ORIGINAL"},
    )
    erro = _assert_erro(duplicado, 409, "IDENTIFICADOR_DUPLICADO")
    assert erro["detalhes"] == {"identificador": "ARM-ORIGINAL"}
    session.rollback()
    assert repositorio.get_by_id(alvo.id).identificador == "ARM-ALVO"

    ausente = client.patch(
        f"/api/armadilhas/{uuid4()}",
        json={"localizacao": "Qualquer lugar"},
    )
    nao_encontrada = _assert_erro(ausente, 404, "ARMADILHA_NAO_ENCONTRADA")
    assert nao_encontrada["detalhes"]["armadilha_id"]
    assert repositorio.get_by_id(original.id).identificador == "ARM-ORIGINAL"


def test_openapi_registra_erros_declarados_para_rotas_de_armadilha(
    client: TestClient,
) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    operacao = response.json()["paths"]["/api/armadilhas"]["post"]
    assert {"201", "409", "422", "500"}.issubset(operacao["responses"])
    resposta_erro = operacao["responses"]["409"]
    assert resposta_erro["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/RespostaErro"
    }
