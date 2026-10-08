"""Testes dos endpoints de análise com arquivos temporários e PostgreSQL."""

import time
from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.dependencias import get_agora, get_inferidor, get_session
from src.api.erros import CodigoErro
from src.entities import Analise, StatusAnalise
from src.inference.contrato import (
    FalhaInferencia,
    PlacaNaoDetectada,
    ResultadoInferencia,
)
from src.repositories.analise_repository import AnaliseRepository
from src.repositories.armadilha_repository import ArmadilhaRepository
from src.repositories.refil_repository import RefilRepository
from src.services.upload import LIMITE_TAMANHO_UPLOAD_BYTES

_AGORA = datetime(2026, 3, 21, 12, 0, tzinfo=timezone.utc)
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
    """Cria a aplicação e direciona os arquivos para a área temporária do teste."""
    for nome, valor in _AMBIENTE_FICTICIO.items():
        monkeypatch.setenv(nome, valor)
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
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


def _imagem(formato: str = "JPEG", tamanho: tuple[int, int] = (512, 512)) -> bytes:
    """Gera conteúdo válido em memória sem depender de rede ou fixture externa."""
    buffer = BytesIO()
    Image.new("RGB", tamanho, (18, 76, 101)).save(buffer, format=formato)
    return buffer.getvalue()


def _criar_armadilha(session: Session, *, com_refil: bool = True):
    """Cria os registros mínimos necessários para uma análise aceita."""
    armadilha = ArmadilhaRepository(session).create(identificador=f"ARM-{uuid4()}")
    refil = None
    if com_refil:
        refil = RefilRepository(session).create(
            armadilha_id=armadilha.id,
            data_instalacao=_AGORA.date(),
        )
    return armadilha, refil


def _erro(response, status_http: int, codigo: CodigoErro) -> dict:
    """Confere o envelope estável sem depender do texto da mensagem."""
    assert response.status_code == status_http
    assert response.headers["content-type"].startswith("application/json")
    assert set(response.json()) == {"erro"}
    erro = response.json()["erro"]
    assert erro["codigo"] == codigo.value
    assert "mensagem" in erro
    return erro


@pytest.mark.parametrize(
    ("formato", "nome", "extensao"),
    [
        ("JPEG", "../../x.jpg", "jpg"),
        ("PNG", "arquivo.jpg", "png"),
    ],
)
def test_post_salva_jpeg_e_png_no_layout_e_get_retorna_mesmo_formato(
    client: TestClient,
    session: Session,
    formato: str,
    nome: str,
    extensao: str,
) -> None:
    armadilha, refil = _criar_armadilha(session)
    assert refil is not None

    response = client.post(
        "/api/analises",
        data={"armadilha_id": str(armadilha.id)},
        files={"imagem": (nome, _imagem(formato), "text/plain")},
    )

    assert response.status_code == 201
    assert response.headers["content-type"].startswith("application/json")
    corpo = response.json()
    assert set(corpo) == {
        "id",
        "refil_id",
        "armadilha_id",
        "analisado_em",
        "percentual_coberto",
        "status",
        "modelo_versao",
        "imagem_url",
        "mascara_url",
    }
    assert corpo["refil_id"] == str(refil.id)
    assert corpo["armadilha_id"] == str(armadilha.id)
    assert corpo["analisado_em"] == "2026-03-21T12:00:00Z"
    assert isinstance(corpo["percentual_coberto"], float)
    assert corpo["percentual_coberto"] == 55.0
    assert corpo["status"] == "atencao"
    assert corpo["modelo_versao"] == "v0.1.0-dev+00000000"

    analise_id = UUID(corpo["id"])
    assert corpo["imagem_url"] == f"/api/analises/{analise_id}/imagem"
    assert corpo["mascara_url"] == f"/api/analises/{analise_id}/mascara"
    pasta = client.app.state.settings.uploads_dir
    caminho_esperado = Path(pasta) / str(analise_id)
    assert (caminho_esperado / f"original.{extensao}").is_file()
    assert (caminho_esperado / "mascara.png").is_file()
    assert not (Path(pasta).parent / "x.jpg").exists()

    detalhe = client.get(f"/api/analises/{analise_id}")
    assert detalhe.status_code == 200
    assert detalhe.json() == corpo
    assert AnaliseRepository(session).get_by_id(analise_id) is not None


def test_post_rejeita_campo_arquivo_ausente_e_formulario_invalido(
    client: TestClient,
) -> None:
    sem_imagem = client.post("/api/analises", data={"armadilha_id": str(uuid4())})
    erro = _erro(sem_imagem, 400, CodigoErro.ARQUIVO_AUSENTE)
    assert erro["detalhes"] == {"campo": "imagem"}

    sem_armadilha = client.post(
        "/api/analises",
        files={"imagem": ("foto.jpg", _imagem(), "image/jpeg")},
    )
    _erro(sem_armadilha, 422, CodigoErro.VALIDACAO_FALHOU)

    uuid_invalido = client.post(
        "/api/analises",
        data={"armadilha_id": "valor-privado"},
        files={"imagem": ("foto.jpg", _imagem(), "image/jpeg")},
    )
    _erro(uuid_invalido, 422, CodigoErro.VALIDACAO_FALHOU)
    assert "valor-privado" not in uuid_invalido.text

    corpo_multipart_invalido = client.post(
        "/api/analises",
        content=b"corpo multipart incompleto",
        headers={"Content-Type": "multipart/form-data"},
    )
    _erro(corpo_multipart_invalido, 400, CodigoErro.REQUISICAO_INVALIDA)


@pytest.mark.parametrize(
    ("nome", "conteudo", "tipo", "codigo"),
    [
        (
            "texto.jpg",
            b"conteudo de texto",
            "image/jpeg",
            CodigoErro.FORMATO_NAO_SUPORTADO,
        ),
        (
            "truncado.png",
            b"\x89PNG\r\n\x1a\n" + b"cabecalho cortado",
            "image/png",
            CodigoErro.FORMATO_NAO_SUPORTADO,
        ),
        (
            "pequena.png",
            _imagem("PNG", (100, 100)),
            "image/png",
            CodigoErro.RESOLUCAO_INSUFICIENTE,
        ),
    ],
)
def test_post_rejeita_formato_corrompido_e_resolucao_baixa(
    client: TestClient,
    session: Session,
    nome: str,
    conteudo: bytes,
    tipo: str,
    codigo: CodigoErro,
) -> None:
    armadilha, _refil = _criar_armadilha(session)

    response = client.post(
        "/api/analises",
        data={"armadilha_id": str(armadilha.id)},
        files={"imagem": (nome, conteudo, tipo)},
    )

    _erro(response, 400, codigo)


def test_post_rejeita_arquivo_acima_de_dez_mib_antes_de_gravar(
    client: TestClient,
    session: Session,
) -> None:
    armadilha, _refil = _criar_armadilha(session)

    response = client.post(
        "/api/analises",
        data={"armadilha_id": str(armadilha.id)},
        files={
            "imagem": (
                "grande.jpg",
                b"x" * (LIMITE_TAMANHO_UPLOAD_BYTES + 1),
                "image/jpeg",
            )
        },
    )

    _erro(response, 413, CodigoErro.ARQUIVO_MUITO_GRANDE)
    assert list(Path(client.app.state.settings.uploads_dir).iterdir()) == []
    assert list(session.scalars(select(Analise))) == []


def test_post_rejeita_armadilha_inexistente_ou_sem_refil_ativo(
    client: TestClient,
    session: Session,
) -> None:
    ausente = client.post(
        "/api/analises",
        data={"armadilha_id": str(uuid4())},
        files={"imagem": ("foto.png", _imagem("PNG"), "image/png")},
    )
    erro_ausente = _erro(ausente, 404, CodigoErro.ARMADILHA_NAO_ENCONTRADA)
    assert erro_ausente["detalhes"]["armadilha_id"]

    armadilha, refil = _criar_armadilha(session, com_refil=False)
    sem_refil = client.post(
        "/api/analises",
        data={"armadilha_id": str(armadilha.id)},
        files={"imagem": ("foto.png", _imagem("PNG"), "image/png")},
    )
    erro_refil = _erro(sem_refil, 409, CodigoErro.REFIL_ATIVO_INEXISTENTE)
    assert erro_refil["detalhes"] == {"armadilha_id": str(armadilha.id)}
    assert refil is None
    assert list(session.scalars(select(Analise))) == []


def test_get_analise_nao_encontrada_e_uuid_invalido_usam_erros_padrao(
    client: TestClient,
) -> None:
    ausente = client.get(f"/api/analises/{uuid4()}")
    erro = _erro(ausente, 404, CodigoErro.ANALISE_NAO_ENCONTRADA)
    assert erro["detalhes"]["analise_id"] in ausente.url.path

    uuid_invalido = client.get("/api/analises/nao-e-uuid")
    _erro(uuid_invalido, 422, CodigoErro.VALIDACAO_FALHOU)


class _InferidorComFalha:
    """Substitui a inferência para exercitar a limpeza após erros controlados."""

    def inferir(self, _conteudo: bytes) -> ResultadoInferencia:
        """Simula falha do modelo sem revelar detalhe técnico na resposta."""
        raise FalhaInferencia("caminho-interno-privado")


class _InferidorSemPlaca:
    """Simula uma imagem em que a superfície adesiva não pode ser localizada."""

    def inferir(self, _conteudo: bytes) -> ResultadoInferencia:
        """Produz a falha de domínio que recebe um código próprio na API."""
        raise PlacaNaoDetectada("detalhe interno privado")


class _InferidorLento:
    """Simula um modelo que ultrapassa o tempo máximo de execução."""

    def inferir(self, _conteudo: bytes) -> ResultadoInferencia:
        """Aguarda além do limite para confirmar a resposta segura de timeout."""
        time.sleep(0.05)
        return ResultadoInferencia(
            percentual_coberto=Decimal("55.00"),
            status=StatusAnalise.ATENCAO,
            modelo_versao="v0.1.0-dev+00000000",
            mascara=b"png",
        )


def _enviar_imagem(client: TestClient, armadilha_id: UUID):
    """Executa um POST válido usado pelos testes de falha transacional."""
    return client.post(
        "/api/analises",
        data={"armadilha_id": str(armadilha_id)},
        files={"imagem": ("foto.jpg", _imagem(), "image/jpeg")},
    )


@pytest.mark.parametrize(
    "falha",
    ["inferencia", "placa", "mascara", "commit", "timeout"],
)
def test_falha_apos_gravacao_remove_todos_os_arquivos_e_registros(
    client: TestClient,
    session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    falha: str,
) -> None:
    from src.services import armazenamento

    armadilha, _refil = _criar_armadilha(session)
    if falha in {"inferencia", "placa", "timeout"}:
        inferidor = {
            "inferencia": _InferidorComFalha,
            "placa": _InferidorSemPlaca,
            "timeout": _InferidorLento,
        }[falha]()
        client.app.dependency_overrides[get_inferidor] = lambda: inferidor
    if falha == "mascara":

        def falhar_gravacao(*_args: object, **_kwargs: object) -> str:
            raise OSError("caminho de armazenamento privado")

        monkeypatch.setattr(armazenamento, "gravar_mascara", falhar_gravacao)
    if falha == "commit":

        def falhar_commit() -> None:
            raise RuntimeError("detalhe privado do banco")

        monkeypatch.setattr(session, "commit", falhar_commit)
    if falha == "timeout":
        from src.api.rotas import analises

        monkeypatch.setattr(analises, "TEMPO_LIMITE_INFERENCIA_SEGUNDOS", 0.001)

    response = _enviar_imagem(client, armadilha.id)

    if falha == "placa":
        codigo = CodigoErro.PLACA_NAO_DETECTADA
    elif falha in {"inferencia", "timeout"}:
        codigo = CodigoErro.FALHA_INFERENCIA
    else:
        codigo = CodigoErro.ERRO_INTERNO
    _erro(response, 500, codigo)
    assert "privado" not in response.text
    assert list(tmp_path.iterdir()) == []
    assert list(session.scalars(select(Analise))) == []
