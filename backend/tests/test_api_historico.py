"""Testes de histórico, downloads de mídia e fluxo completo da análise."""

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import event
from sqlalchemy.orm import Session

from src.api.dependencias import get_agora, get_session
from src.api.erros import CodigoErro
from src.entities import Analise, StatusAnalise
from src.repositories.analise_repository import AnaliseRepository
from src.repositories.armadilha_repository import ArmadilhaRepository
from src.repositories.refil_repository import RefilRepository

_AGORA = datetime(2026, 3, 21, 12, tzinfo=timezone.utc)
_AMBIENTE_FICTICIO = {
    "DATABASE_URL": "postgresql://db-ficticio:5432/armadilhas",
    "MODEL_WEIGHTS_PATH": "/caminho-ficticio/pesos.pt",
    "MODEL_VERSION": "v0.1.0-dev",
    "CORS_ORIGENS": "http://localhost:5173",
}


@pytest.fixture
def client(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> TestClient:
    """Aponta os uploads de cada teste para um diretório temporário externo ao repo."""
    for nome, valor in _AMBIENTE_FICTICIO.items():
        monkeypatch.setenv(nome, valor)
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("LIMIAR_ATENCAO", "40")
    monkeypatch.setenv("LIMIAR_TROCAR", "70")

    from src.main import create_app

    app = create_app()

    def substituir_sessao():
        yield session

    app.dependency_overrides[get_session] = substituir_sessao
    app.dependency_overrides[get_agora] = lambda: _AGORA
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _criar_analise(
    session: Session,
    refil_id: UUID,
    analisado_em: datetime,
    *,
    percentual: Decimal = Decimal("35.50"),
) -> Analise:
    """Persiste uma leitura sintética para os cenários que não testam upload."""
    return AnaliseRepository(session).create(
        refil_id=refil_id,
        analisado_em=analisado_em,
        percentual_coberto=percentual,
        status=StatusAnalise.OK,
        caminho_imagem="sem-arquivo/original.jpg",
        modelo_versao="v1.0.0+12345678",
    )


def _criar_armadilha(session: Session, *, identificador: str = "ARM-HIST"):
    """Cria uma armadilha com um refil ativo para os testes de histórico."""
    armadilha = ArmadilhaRepository(session).create(identificador=identificador)
    refil = RefilRepository(session).create(
        armadilha_id=armadilha.id,
        data_instalacao=date(2026, 2, 1),
    )
    return armadilha, refil


def _imagem(formato: str = "JPEG") -> bytes:
    """Gera uma imagem compatível com a resolução mínima da API."""
    buffer = BytesIO()
    Image.new("RGB", (512, 512), (38, 91, 122)).save(buffer, format=formato)
    return buffer.getvalue()


def _criar_analise_por_upload(
    client: TestClient,
    armadilha_id: UUID,
    *,
    formato: str = "JPEG",
) -> tuple[UUID, bytes, str]:
    """Usa o POST real para gravar a imagem e a máscara de uma análise."""
    conteudo = _imagem(formato)
    resposta = client.post(
        "/api/analises",
        data={"armadilha_id": str(armadilha_id)},
        files={"imagem": (f"foto.{formato.lower()}", conteudo, "image/unknown")},
    )
    assert resposta.status_code == 201
    extensao = "jpg" if formato == "JPEG" else "png"
    return UUID(resposta.json()["id"]), conteudo, extensao


def _erro(response, status_code: int, codigo: CodigoErro) -> dict:
    """Confere o envelope público padrão e devolve o objeto interno do erro."""
    assert response.status_code == status_code
    assert response.headers["content-type"].startswith("application/json")
    assert set(response.json()) == {"erro"}
    erro = response.json()["erro"]
    assert erro["codigo"] == codigo.value
    return erro


def test_historico_seleciona_escopos_refil_e_monta_saida_cronologica(
    client: TestClient,
    session: Session,
) -> None:
    """Inclui os campos públicos e honra escopo, ciclo específico e cronologia."""
    armadilha = ArmadilhaRepository(session).create(identificador="ARM-ESCOPO")
    repositorio_refil = RefilRepository(session)
    refil_anterior = repositorio_refil.create(
        armadilha_id=armadilha.id,
        data_instalacao=date(2026, 1, 1),
        data_troca=date(2026, 2, 1),
    )
    refil_ativo = repositorio_refil.create(
        armadilha_id=armadilha.id,
        data_instalacao=date(2026, 2, 1),
    )
    antiga_1 = _criar_analise(
        session,
        refil_anterior.id,
        datetime(2026, 1, 5, 8, tzinfo=timezone.utc),
    )
    antiga_2 = _criar_analise(
        session,
        refil_anterior.id,
        datetime(2026, 1, 20, 8, tzinfo=timezone.utc),
    )
    atual_1 = _criar_analise(
        session,
        refil_ativo.id,
        datetime(2026, 3, 3, 8, tzinfo=timezone.utc),
    )
    atual_2 = _criar_analise(
        session,
        refil_ativo.id,
        datetime(2026, 3, 10, 8, tzinfo=timezone.utc),
    )
    url = f"/api/armadilhas/{armadilha.id}/analises"

    padrao = client.get(url)
    ativo_explicito = client.get(url, params={"escopo": "refil_ativo"})
    completo = client.get(url, params={"escopo": "completo"})
    ciclo_especifico = client.get(
        url,
        params={"escopo": "refil_ativo", "refil_id": str(refil_anterior.id)},
    )

    assert (
        padrao.status_code == ativo_explicito.status_code == completo.status_code == 200
    )
    assert [item["id"] for item in padrao.json()] == [str(atual_1.id), str(atual_2.id)]
    assert [item["id"] for item in completo.json()] == [
        str(antiga_1.id),
        str(antiga_2.id),
        str(atual_1.id),
        str(atual_2.id),
    ]
    assert [item["id"] for item in ciclo_especifico.json()] == [
        str(antiga_1.id),
        str(antiga_2.id),
    ]
    item = completo.json()[0]
    assert item["refil_id"] == str(refil_anterior.id)
    assert item["armadilha_id"] == str(armadilha.id)
    assert item["percentual_coberto"] == 35.5
    assert item["analisado_em"] == "2026-01-05T08:00:00Z"


def test_historico_limita_as_mais_recentes_e_devolve_em_ordem_crescente(
    client: TestClient,
    session: Session,
) -> None:
    """Seleciona o limite mais recente e mantém a apresentação cronológica."""
    armadilha, refil = _criar_armadilha(session, identificador="ARM-LIMITE")
    analises = [
        _criar_analise(
            session,
            refil.id,
            datetime(2026, 3, 1, tzinfo=timezone.utc) + timedelta(days=dia),
        )
        for dia in range(5)
    ]
    url = f"/api/armadilhas/{armadilha.id}/analises"

    um = client.get(url, params={"limite": 1})
    mil = client.get(url, params={"limite": 1000})

    assert [item["id"] for item in um.json()] == [str(analises[-1].id)]
    assert [item["id"] for item in mil.json()] == [str(item.id) for item in analises]


@pytest.mark.parametrize(
    "parametros",
    [
        {"escopo": "desconhecido"},
        {"limite": "0"},
        {"limite": "1001"},
        {"limite": "texto"},
        {"refil_id": "uuid-invalido"},
    ],
)
def test_historico_rejeita_parametros_invalidos(
    client: TestClient,
    parametros: dict[str, str],
) -> None:
    """Devolve validação 422 para escopo, UUID e limites inválidos."""
    response = client.get(f"/api/armadilhas/{uuid4()}/analises", params=parametros)

    erro = _erro(response, 422, CodigoErro.VALIDACAO_FALHOU)
    assert erro["detalhes"]["campos_invalidos"]


def test_historico_rejeita_uuid_de_armadilha_invalido(client: TestClient) -> None:
    """Deixa a validação de UUID do caminho produzir o erro 422 padrão."""
    response = client.get("/api/armadilhas/nao-e-uuid/analises")

    _erro(response, 422, CodigoErro.VALIDACAO_FALHOU)


def test_historico_rejeita_refil_inexistente_e_de_outra_armadilha(
    client: TestClient,
    session: Session,
) -> None:
    """Oculta se o ciclo existe fora da armadilha consultada."""
    armadilha, _refil = _criar_armadilha(session, identificador="ARM-PROPRIA")
    armadilha_estranha, refil_estranho = _criar_armadilha(
        session,
        identificador="ARM-ALHEIA",
    )
    _criar_analise(
        session,
        refil_estranho.id,
        datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    url = f"/api/armadilhas/{armadilha.id}/analises"

    por_outra = client.get(url, params={"refil_id": str(refil_estranho.id)})
    inexistente = client.get(url, params={"refil_id": str(uuid4())})

    erro_outra = _erro(por_outra, 422, CodigoErro.VALIDACAO_FALHOU)
    erro_inexistente = _erro(inexistente, 422, CodigoErro.VALIDACAO_FALHOU)
    assert (
        erro_outra["detalhes"] == erro_inexistente["detalhes"] == {"campo": "refil_id"}
    )
    assert str(armadilha_estranha.id) not in por_outra.text
    assert str(refil_estranho.id) not in por_outra.text


def test_historico_inexistente_e_armadilha_sem_refil_ativo(
    client: TestClient,
    session: Session,
) -> None:
    """Distingue armadilha ausente de armadilha sem ciclo atual."""
    ausente = client.get(f"/api/armadilhas/{uuid4()}/analises")
    erro_ausente = _erro(ausente, 404, CodigoErro.ARMADILHA_NAO_ENCONTRADA)
    assert erro_ausente["detalhes"]["armadilha_id"]

    armadilha = ArmadilhaRepository(session).create(identificador="ARM-SEM-ATIVO")
    refil = RefilRepository(session).create(
        armadilha_id=armadilha.id,
        data_instalacao=date(2026, 1, 1),
        data_troca=date(2026, 2, 1),
    )
    analise = _criar_analise(
        session,
        refil.id,
        datetime(2026, 1, 20, tzinfo=timezone.utc),
    )
    url = f"/api/armadilhas/{armadilha.id}/analises"

    ativo = client.get(url)
    completo = client.get(url, params={"escopo": "completo"})

    assert ativo.status_code == 200
    assert ativo.json() == []
    assert [item["id"] for item in completo.json()] == [str(analise.id)]


def test_consultas_de_historico_nao_crescem_com_a_quantidade_de_analises(
    client: TestClient,
    session: Session,
) -> None:
    """Compara consultas para cinco e cinquenta análises de refis distintos."""
    armadilha = ArmadilhaRepository(session).create(identificador="ARM-SEM-N-MAIS-UM")
    repositorio_refil = RefilRepository(session)
    for indice in range(50):
        refil = repositorio_refil.create(
            armadilha_id=armadilha.id,
            data_instalacao=date(2026, 1, 1) + timedelta(days=indice),
            data_troca=date(2026, 4, 1),
        )
        _criar_analise(
            session,
            refil.id,
            datetime(2026, 5, 1, tzinfo=timezone.utc) + timedelta(minutes=indice),
        )

    engine = session.get_bind()
    medindo = False
    consultas = 0

    def contar_consulta(*_args) -> None:
        nonlocal consultas
        if medindo:
            consultas += 1

    def medir(limite: int) -> tuple[int, int]:
        nonlocal consultas, medindo
        session.expire_all()
        consultas = 0
        medindo = True
        response = client.get(
            f"/api/armadilhas/{armadilha.id}/analises",
            params={"escopo": "completo", "limite": limite},
        )
        medindo = False
        assert response.status_code == 200
        assert len(response.json()) == limite
        return consultas, len(response.json())

    event.listen(engine, "before_cursor_execute", contar_consulta)
    try:
        consultas_cinco, quantidade_cinco = medir(5)
        consultas_cinquenta, quantidade_cinquenta = medir(50)
    finally:
        medindo = False
        event.remove(engine, "before_cursor_execute", contar_consulta)

    assert (quantidade_cinco, quantidade_cinquenta) == (5, 50)
    assert consultas_cinco == consultas_cinquenta


@pytest.mark.parametrize(
    ("formato", "tipo_midia"),
    [("JPEG", "image/jpeg"), ("PNG", "image/png")],
)
def test_downloads_de_imagem_e_mascara_preservam_binarios_e_cache(
    client: TestClient,
    session: Session,
    formato: str,
    tipo_midia: str,
) -> None:
    """Verifica bytes, tipos, cache, ETag e resposta condicional das duas mídias."""
    armadilha, _refil = _criar_armadilha(session, identificador=f"ARM-{formato}")
    analise_id, original, extensao = _criar_analise_por_upload(
        client,
        armadilha.id,
        formato=formato,
    )
    raiz = Path(client.app.state.settings.uploads_dir) / str(analise_id)
    imagem = client.get(f"/api/analises/{analise_id}/imagem")
    mascara = client.get(f"/api/analises/{analise_id}/mascara")

    assert imagem.status_code == mascara.status_code == 200
    assert imagem.content == original == (raiz / f"original.{extensao}").read_bytes()
    assert imagem.headers["content-type"] == tipo_midia
    assert mascara.headers["content-type"] == "image/png"
    assert mascara.content == (raiz / "mascara.png").read_bytes()
    for response in (imagem, mascara):
        assert response.headers["cache-control"] == (
            "private, max-age=31536000, immutable"
        )
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["content-disposition"] == "inline"
        assert response.headers["etag"]
        assert response.headers["last-modified"]
        condicional = client.get(
            response.request.url.path,
            headers={"If-None-Match": response.headers["etag"]},
        )
        assert condicional.status_code == 304
        assert condicional.content == b""


@pytest.mark.parametrize("recurso", ["imagem", "mascara"])
def test_download_rejeita_analise_ou_arquivo_ausente(
    client: TestClient,
    session: Session,
    recurso: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Usa o envelope JSON padrão para registros e arquivos inexistentes."""
    inexistente = client.get(f"/api/analises/{uuid4()}/{recurso}")
    erro_analise = _erro(
        inexistente,
        404,
        CodigoErro.ANALISE_NAO_ENCONTRADA,
    )
    assert erro_analise["detalhes"]["analise_id"]

    armadilha, _refil = _criar_armadilha(session, identificador=f"ARM-SEM-{recurso}")
    analise_id, _conteudo, extensao = _criar_analise_por_upload(client, armadilha.id)
    raiz = Path(client.app.state.settings.uploads_dir) / str(analise_id)
    arquivo = raiz / (f"original.{extensao}" if recurso == "imagem" else "mascara.png")
    arquivo.unlink()

    with caplog.at_level(logging.WARNING):
        ausente = client.get(f"/api/analises/{analise_id}/{recurso}")

    erro_arquivo = _erro(ausente, 404, CodigoErro.ANALISE_NAO_ENCONTRADA)
    assert erro_arquivo["detalhes"] == {"recurso": recurso}
    assert "uploads" not in ausente.text.lower()
    assert "ausente ou inválido" in caplog.text


@pytest.mark.parametrize("tipo_caminho", ["relativo", "absoluto", "extensao"])
def test_download_nao_le_caminho_adulterado_fora_da_raiz(
    client: TestClient,
    session: Session,
    tmp_path: Path,
    tipo_caminho: str,
) -> None:
    """Rejeita travessia e caminho absoluto sem servir conteúdo externo."""
    armadilha, _refil = _criar_armadilha(
        session, identificador=f"ARM-PATH-{tipo_caminho}"
    )
    analise_id, _conteudo, _extensao = _criar_analise_por_upload(client, armadilha.id)
    arquivo_externo = tmp_path / "fora.jpg"
    arquivo_externo.write_bytes(b"conteudo privado fora da raiz")
    analise = AnaliseRepository(session).get_by_id(analise_id)
    assert analise is not None
    if tipo_caminho == "relativo":
        analise.caminho_imagem = "../../etc/passwd"
    elif tipo_caminho == "absoluto":
        analise.caminho_imagem = str(arquivo_externo)
    else:
        analise.caminho_imagem = f"{analise_id}/original.gif"
    session.flush()

    response = client.get(f"/api/analises/{analise_id}/imagem")

    erro = _erro(response, 404, CodigoErro.ANALISE_NAO_ENCONTRADA)
    assert erro["detalhes"] == {"recurso": "imagem"}
    assert b"conteudo privado fora da raiz" not in response.content
    assert str(arquivo_externo) not in response.text


def test_download_rejeita_symlink_da_mascara_para_fora_da_raiz(
    client: TestClient,
    session: Session,
    tmp_path: Path,
) -> None:
    """Impede que uma máscara redirecione FileResponse para um arquivo externo."""
    armadilha, _refil = _criar_armadilha(session, identificador="ARM-SYMLINK")
    analise_id, _conteudo, _extensao = _criar_analise_por_upload(client, armadilha.id)
    mascara = (
        Path(client.app.state.settings.uploads_dir) / str(analise_id) / "mascara.png"
    )
    arquivo_externo = tmp_path / "mascara-privada.png"
    arquivo_externo.write_bytes(b"conteudo privado externo")
    mascara.unlink()
    mascara.symlink_to(arquivo_externo)

    response = client.get(f"/api/analises/{analise_id}/mascara")

    erro = _erro(response, 404, CodigoErro.ANALISE_NAO_ENCONTRADA)
    assert erro["detalhes"] == {"recurso": "mascara"}
    assert b"conteudo privado externo" not in response.content


def test_download_mascara_usa_o_uuid_em_vez_do_caminho_do_banco(
    client: TestClient,
    session: Session,
) -> None:
    """Deriva o endereço da máscara do UUID mesmo com caminho original adulterado."""
    armadilha, _refil = _criar_armadilha(session, identificador="ARM-MASCARA-ID")
    analise_id, _conteudo, _extensao = _criar_analise_por_upload(client, armadilha.id)
    analise = AnaliseRepository(session).get_by_id(analise_id)
    assert analise is not None
    analise.caminho_imagem = "../../etc/passwd"
    session.flush()

    response = client.get(f"/api/analises/{analise_id}/mascara")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert (
        response.content
        == (
            Path(client.app.state.settings.uploads_dir)
            / str(analise_id)
            / "mascara.png"
        ).read_bytes()
    )


def test_fluxo_completo_de_historico_download_e_troca(
    client: TestClient,
) -> None:
    """Percorre cadastro, três análises, downloads, troca e os dois escopos."""
    criada = client.post(
        "/api/armadilhas",
        json={
            "identificador": f"ARM-FLUXO-{uuid4()}",
            "data_instalacao": "2026-03-01",
            "criar_refil_inicial": True,
        },
    )
    assert criada.status_code == 201
    armadilha_id = UUID(criada.json()["id"])
    for _ in range(3):
        _criar_analise_por_upload(client, armadilha_id)

    base = f"/api/armadilhas/{armadilha_id}/analises"
    antes = client.get(base)
    assert antes.status_code == 200
    assert len(antes.json()) == 3
    analise_id = UUID(antes.json()[0]["id"])
    assert client.get(f"/api/analises/{analise_id}/imagem").status_code == 200
    assert client.get(f"/api/analises/{analise_id}/mascara").status_code == 200

    troca = client.post(
        f"/api/armadilhas/{armadilha_id}/refis",
        json={"data_instalacao": "2026-03-21"},
    )
    assert troca.status_code == 201
    ativo = client.get(base)
    completo = client.get(base, params={"escopo": "completo"})

    assert ativo.status_code == completo.status_code == 200
    assert ativo.json() == []
    assert len(completo.json()) == 3
    assert {item["refil_id"] for item in completo.json()} == {
        criada.json()["refil_ativo"]["id"]
    }
