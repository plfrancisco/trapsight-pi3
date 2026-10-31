"""Testes da foto de identificação da armadilha (envio, leitura e remoção)."""

from datetime import datetime, timezone
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from src.api.dependencias import get_agora, get_session
from src.entities.papel import PapelUsuario
from src.repositories.armadilha_repository import ArmadilhaRepository
from src.services.upload import LIMITE_TAMANHO_UPLOAD_BYTES
from tests.auth_helpers import (
    aplicar_credenciais,
    autenticar_cliente,
    criar_sessao,
    criar_usuario,
)

_AGORA = datetime(2026, 3, 21, 12, 0, tzinfo=timezone.utc)
_AMBIENTE_FICTICIO = {
    "DATABASE_URL": "postgresql://db-ficticio:5432/armadilhas",
    "MODEL_WEIGHTS_PATH": "/caminho-ficticio/pesos.pt",
    "MODEL_VERSION": "v0.1.0-dev",
    "INFERENCE_MODE": "stub",
    "UPLOADS_DIR": "/diretorio-ficticio/uploads",
    "CORS_ORIGENS": "http://localhost:5173",
}


@pytest.fixture
def client(session: Session, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Cria a API com a sessão transacional do teste e um operador autenticado."""
    for nome, valor in _AMBIENTE_FICTICIO.items():
        monkeypatch.setenv(nome, valor)

    from src.main import create_app

    app = create_app()

    def substituir_sessao() -> Session:
        yield session

    app.dependency_overrides[get_session] = substituir_sessao
    app.dependency_overrides[get_agora] = lambda: _AGORA
    with TestClient(app) as test_client:
        autenticar_cliente(test_client, session)
        yield test_client
    app.dependency_overrides.clear()


def _imagem(formato: str, tamanho=(1600, 1200), exif: bool = False) -> bytes:
    """Gera uma imagem com ruído, para o JPEG não ficar trivial."""
    imagem = Image.effect_noise(tamanho, 40)
    if formato == "JPEG":
        imagem = imagem.convert("RGB")  # PNG fica em tons de cinza para caber em 4 MB
    buffer = BytesIO()
    argumentos = {}
    if exif:
        dados = Image.Exif()
        dados[0x010F] = "FabricanteSecreto"  # Make
        dados[0x0132] = "2026:01:02 03:04:05"  # DateTime
        argumentos["exif"] = dados
    imagem.save(buffer, format=formato, **argumentos)
    return buffer.getvalue()


def _enviar(client: TestClient, armadilha_id, conteudo: bytes, tipo="image/jpeg"):
    return client.put(
        f"/api/armadilhas/{armadilha_id}/foto",
        files={"arquivo": ("foto.bin", conteudo, tipo)},
    )


@pytest.mark.parametrize(
    ("formato", "tipo"), [("JPEG", "image/jpeg"), ("PNG", "image/png")]
)
def test_envio_valido_reduz_para_800px_e_serve_jpeg(
    client: TestClient, session: Session, formato: str, tipo: str
) -> None:
    armadilha = ArmadilhaRepository(session).create(identificador="ARM-FOTO")

    resposta = _enviar(client, armadilha.id, _imagem(formato), tipo)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["foto_tipo"] == "real"
    assert corpo["foto_url"].startswith(f"/api/armadilhas/{armadilha.id}/foto?v=")
    leitura = client.get(f"/api/armadilhas/{armadilha.id}/foto")
    assert leitura.status_code == 200
    assert leitura.headers["content-type"] == "image/jpeg"
    assert leitura.headers["x-content-type-options"] == "nosniff"
    assert "private" in leitura.headers["cache-control"]
    with Image.open(BytesIO(leitura.content)) as foto:
        assert foto.format == "JPEG"
        assert max(foto.size) == 800
    assert len(leitura.content) < LIMITE_TAMANHO_UPLOAD_BYTES


def test_exif_e_removido_da_copia_guardada(
    client: TestClient, session: Session
) -> None:
    armadilha = ArmadilhaRepository(session).create(identificador="ARM-EXIF")
    original = _imagem("JPEG", exif=True)
    with Image.open(BytesIO(original)) as imagem:
        assert imagem.getexif().get(0x010F) == "FabricanteSecreto"

    _enviar(client, armadilha.id, original)
    leitura = client.get(f"/api/armadilhas/{armadilha.id}/foto")

    with Image.open(BytesIO(leitura.content)) as foto:
        assert len(foto.getexif()) == 0
        assert "exif" not in foto.info
    assert b"FabricanteSecreto" not in leitura.content


def test_listagem_e_detalhe_informam_o_tipo_da_foto(
    client: TestClient, session: Session
) -> None:
    com_foto = ArmadilhaRepository(session).create(identificador="ARM-A-FOTO")
    sem_foto = ArmadilhaRepository(session).create(identificador="ARM-B-PADRAO")
    _enviar(client, com_foto.id, _imagem("JPEG"))

    itens = {i["identificador"]: i for i in client.get("/api/armadilhas").json()}
    detalhe = client.get(f"/api/armadilhas/{com_foto.id}").json()
    padrao = client.get(f"/api/armadilhas/{sem_foto.id}").json()

    assert itens["ARM-A-FOTO"]["foto_tipo"] == "real"
    assert itens["ARM-A-FOTO"]["foto_url"].startswith(
        f"/api/armadilhas/{com_foto.id}/foto?v="
    )
    assert itens["ARM-B-PADRAO"]["foto_tipo"] == "padrao"
    assert itens["ARM-B-PADRAO"]["foto_url"] is None
    assert detalhe["foto_tipo"] == "real"
    assert padrao["foto_tipo"] == "padrao"
    assert padrao["foto_url"] is None


def test_delete_volta_ao_padrao_e_e_idempotente(
    client: TestClient, session: Session
) -> None:
    armadilha = ArmadilhaRepository(session).create(identificador="ARM-DEL")
    _enviar(client, armadilha.id, _imagem("JPEG"))

    primeiro = client.delete(f"/api/armadilhas/{armadilha.id}/foto")
    segundo = client.delete(f"/api/armadilhas/{armadilha.id}/foto")

    assert primeiro.status_code == 204
    assert segundo.status_code == 204
    assert client.get(f"/api/armadilhas/{armadilha.id}/foto").status_code == 404
    assert client.get(f"/api/armadilhas/{armadilha.id}").json()["foto_tipo"] == "padrao"


def test_nova_foto_muda_a_versao_da_url(client: TestClient, session: Session) -> None:
    armadilha = ArmadilhaRepository(session).create(identificador="ARM-VER")
    primeira = _enviar(client, armadilha.id, _imagem("JPEG")).json()["foto_url"]
    ArmadilhaRepository(session).definir_foto(
        armadilha.id, b"\xff\xd8\xff", datetime(2026, 1, 1, tzinfo=timezone.utc)
    )

    detalhe = client.get(f"/api/armadilhas/{armadilha.id}").json()

    assert detalhe["foto_url"] != primeira


def test_armadilha_inexistente_ou_sem_foto_responde_404_padrao(
    client: TestClient, session: Session
) -> None:
    sem_foto = ArmadilhaRepository(session).create(identificador="ARM-SEM")
    inexistente = "00000000-0000-0000-0000-000000000001"

    for url in (
        f"/api/armadilhas/{sem_foto.id}/foto",
        f"/api/armadilhas/{inexistente}/foto",
    ):
        resposta = client.get(url)
        assert resposta.status_code == 404
        assert resposta.json()["erro"]["codigo"] == "ARMADILHA_NAO_ENCONTRADA"
    assert _enviar(client, inexistente, _imagem("JPEG")).status_code == 404
    assert client.delete(f"/api/armadilhas/{inexistente}/foto").status_code == 404


def test_armadilha_removida_nao_serve_nem_aceita_foto(
    client: TestClient, session: Session
) -> None:
    armadilha = ArmadilhaRepository(session).create(identificador="ARM-REM")
    _enviar(client, armadilha.id, _imagem("JPEG"))
    ArmadilhaRepository(session).remover(armadilha.id, _AGORA)

    assert client.get(f"/api/armadilhas/{armadilha.id}/foto").status_code == 404
    assert _enviar(client, armadilha.id, _imagem("JPEG")).status_code == 404


def test_validacoes_do_arquivo(client: TestClient, session: Session) -> None:
    armadilha = ArmadilhaRepository(session).create(identificador="ARM-VAL")

    texto = _enviar(client, armadilha.id, b"isto nao e imagem")
    pequena = _enviar(client, armadilha.id, _imagem("JPEG", tamanho=(300, 300)))
    grande = _enviar(
        client, armadilha.id, b"\xff\xd8\xff" + b"x" * (LIMITE_TAMANHO_UPLOAD_BYTES + 1)
    )
    buffer = BytesIO()
    Image.new("L", (5000, 4001), 200).save(buffer, format="PNG")
    pixels = _enviar(client, armadilha.id, buffer.getvalue(), "image/png")
    ausente = client.put(
        f"/api/armadilhas/{armadilha.id}/foto",
        files={"outro": ("a.jpg", b"x", "image/jpeg")},
    )

    assert texto.status_code == 400
    assert texto.json()["erro"]["codigo"] == "FORMATO_NAO_SUPORTADO"
    assert pequena.status_code == 400
    assert pequena.json()["erro"]["codigo"] == "RESOLUCAO_INSUFICIENTE"
    assert grande.status_code == 413
    assert grande.json()["erro"]["detalhes"] == {"motivo": "bytes"}
    assert pixels.status_code == 413
    assert pixels.json()["erro"]["detalhes"] == {"motivo": "pixels"}
    assert ausente.status_code == 400
    assert ausente.json()["erro"]["codigo"] == "ARQUIVO_AUSENTE"
    assert client.get(f"/api/armadilhas/{armadilha.id}").json()["foto_tipo"] == "padrao"


def test_corpo_acima_do_limite_e_barrado_pelo_middleware(
    client: TestClient, session: Session
) -> None:
    armadilha = ArmadilhaRepository(session).create(identificador="ARM-MW")
    corpo = b"x" * (LIMITE_TAMANHO_UPLOAD_BYTES + 2 * 1024 * 1024)

    resposta = client.put(
        f"/api/armadilhas/{armadilha.id}/foto",
        files={"arquivo": ("f.jpg", corpo, "image/jpeg")},
    )

    assert resposta.status_code == 413
    assert resposta.json()["erro"]["detalhes"] == {"motivo": "bytes"}


def test_sem_sessao_responde_401_e_sem_csrf_403(
    client: TestClient, session: Session
) -> None:
    armadilha = ArmadilhaRepository(session).create(identificador="ARM-SEG")
    _enviar(client, armadilha.id, _imagem("JPEG"))
    url = f"/api/armadilhas/{armadilha.id}/foto"

    token = client.headers.pop("X-CSRF-Token")
    sem_csrf_put = client.put(
        url, files={"arquivo": ("f.jpg", _imagem("JPEG"), "image/jpeg")}
    )
    sem_csrf_delete = client.delete(url)
    client.headers["X-CSRF-Token"] = token
    cookies = dict(client.cookies)
    client.cookies.clear()
    anonimo = client.get(url)
    client.cookies.update(cookies)

    assert sem_csrf_put.status_code == 403
    assert sem_csrf_put.json()["erro"]["codigo"] == "CSRF_INVALIDO"
    assert sem_csrf_delete.status_code == 403
    assert anonimo.status_code == 401


def test_gerente_tambem_pode_enviar_e_remover(
    client: TestClient, session: Session
) -> None:
    armadilha = ArmadilhaRepository(session).create(identificador="ARM-GER")
    gerente = criar_usuario(
        session, client.app, email="gerente@exemplo.com", papel=PapelUsuario.GERENTE
    )
    aplicar_credenciais(client, criar_sessao(session, client.app, gerente))

    enviado = _enviar(client, armadilha.id, _imagem("JPEG"))
    removido = client.delete(f"/api/armadilhas/{armadilha.id}/foto")

    assert enviado.status_code == 200
    assert removido.status_code == 204


def test_leitura_condicional_devolve_304(client: TestClient, session: Session) -> None:
    armadilha = ArmadilhaRepository(session).create(identificador="ARM-304")
    _enviar(client, armadilha.id, _imagem("JPEG"))
    url = f"/api/armadilhas/{armadilha.id}/foto"
    etag = client.get(url).headers["etag"]

    resposta = client.get(url, headers={"If-None-Match": etag})

    assert resposta.status_code == 304
    assert resposta.content == b""
