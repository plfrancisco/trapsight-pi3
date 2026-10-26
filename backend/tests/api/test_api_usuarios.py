"""Autorização e contratos da criação e listagem de contas."""

from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from src.api.dependencias import get_session
from src.entities import Sessao, Usuario
from src.entities.papel import PapelUsuario
from tests.auth_helpers import aplicar_credenciais, criar_sessao, criar_usuario

_SENHA = "uma frase longa e bem diferente 2026"
_CORPO = {"email": "nova@exemplo.com", "nome": "Nova Pessoa", "senha": _SENHA}
_AGORA = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)


@pytest.fixture
def client(session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Compartilha a transação do teste com middleware e rotas HTTP."""
    for chave, valor in {
        "DATABASE_URL": "postgresql://db-ficticio:5432/armadilhas",
        "MODEL_WEIGHTS_PATH": "/tmp/ausente.pt",
        "MODEL_VERSION": "v0.1.0-test",
        "INFERENCE_MODE": "stub",
        "CORS_ORIGENS": "http://localhost:5173",
        "UPLOADS_DIR": str(tmp_path),
    }.items():
        monkeypatch.setenv(chave, valor)
    from src.main import create_app

    app = create_app()

    def obter_sessao():
        yield session

    app.dependency_overrides[get_session] = obter_sessao
    app.state.provedor_de_sessao = lambda: nullcontext(session)
    app.state.relogio = lambda: _AGORA
    with TestClient(app) as cliente:
        yield cliente


def _autenticar(client, session, papel=PapelUsuario.GERENTE):
    usuario = criar_usuario(session, client.app, papel=papel)
    aplicar_credenciais(client, criar_sessao(session, client.app, usuario))
    return usuario


@pytest.mark.parametrize("metodo", ["GET", "POST"])
@pytest.mark.parametrize("papel", [None, PapelUsuario.OPERADOR, PapelUsuario.GERENTE])
def test_endpoints_exigem_gerente(client, session, metodo, papel):
    if papel is not None:
        _autenticar(client, session, papel)
    resposta = client.request(
        metodo, "/api/usuarios", **({"json": _CORPO} if metodo == "POST" else {})
    )
    esperado = (
        401
        if papel is None
        else 403
        if papel == PapelUsuario.OPERADOR
        else 201
        if metodo == "POST"
        else 200
    )
    assert resposta.status_code == esperado
    if papel == PapelUsuario.OPERADOR:
        assert resposta.json()["erro"]["codigo"] == "ACESSO_NEGADO"


def test_criacao_e_lista_so_expoem_campos_publicos(client, session, caplog):
    gerente = _autenticar(client, session)
    with caplog.at_level("INFO", logger="trapsight.auditoria"):
        resposta = client.post("/api/usuarios", json=_CORPO)
    assert resposta.status_code == 201
    conta = resposta.json()
    assert set(conta) == {
        "id",
        "email",
        "nome",
        "papel",
        "ativo",
        "ultimo_login_em",
        "criado_em",
    }
    assert conta["ativo"] is True
    assert conta["papel"] == "operador"
    assert conta["ultimo_login_em"] is None
    criado = session.scalars(
        select(Usuario).where(Usuario.email == _CORPO["email"])
    ).one()
    assert (
        session.scalar(
            select(func.count())
            .select_from(Sessao)
            .where(Sessao.usuario_id == criado.id)
        )
        == 0
    )
    assert session.get(Usuario, criado.id).senha_hash.startswith("$argon2id$")
    lista = client.get("/api/usuarios")
    assert lista.status_code == 200
    assert lista.headers["Cache-Control"] == "no-store"
    assert [item["email"] for item in lista.json()] == sorted(
        item["email"] for item in lista.json()
    )
    assert _SENHA not in resposta.text + lista.text + caplog.text
    assert "senha_hash" not in resposta.text + lista.text + caplog.text
    assert "auth.conta_criada" in caplog.text
    assert f"criado_por_id={gerente.id}" in caplog.text


@pytest.mark.parametrize(
    "campo,valor", [("papel", "gerente"), ("ativo", False), ("senha_hash", "x")]
)
def test_cliente_nao_define_privilegios(client, session, campo, valor):
    _autenticar(client, session)
    resposta = client.post("/api/usuarios", json={**_CORPO, campo: valor})
    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "VALIDACAO_FALHOU"


def test_post_exige_csrf(client, session):
    _autenticar(client, session)
    del client.headers["X-CSRF-Token"]
    resposta = client.post("/api/usuarios", json=_CORPO)
    assert resposta.status_code == 403
    assert resposta.json()["erro"]["codigo"] == "CSRF_INVALIDO"


@pytest.mark.parametrize(
    "email", ["OPERADOR@EXEMPLO.COM", "ｏｐｅｒａｄｏｒ@exemplo.com"]
)
def test_email_normalizado_duplicado_e_conflito(client, session, email):
    _autenticar(client, session)
    resposta = client.post("/api/usuarios", json={**_CORPO, "email": email})
    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "EMAIL_JA_CADASTRADO"


def test_senha_fraca_nao_cria_conta_nem_vaza_senha(client, session, caplog):
    _autenticar(client, session)
    resposta = client.post("/api/usuarios", json={**_CORPO, "senha": "senha-fraca"})
    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "SENHA_FRACA"
    assert "senha-fraca" not in resposta.text + caplog.text
    assert session.scalar(select(func.count()).select_from(Usuario)) == 1


def test_autorizacao_consulta_papel_atual_do_banco(client, session, caplog):
    gerente = _autenticar(client, session)
    assert client.get("/api/usuarios").status_code == 200
    session.execute(
        update(Usuario).where(Usuario.id == gerente.id).values(papel="operador"),
        execution_options={"synchronize_session": False},
    )
    with caplog.at_level("INFO", logger="trapsight.auditoria"):
        resposta = client.get("/api/usuarios")
    assert resposta.status_code == 403
    assert "auth.acesso_negado" in caplog.text


def test_login_e_me_devolvem_papel(client, session):
    criar_usuario(session, client.app, papel=PapelUsuario.GERENTE)
    client.headers["Origin"] = "http://localhost:5173"
    resposta = client.post(
        "/api/auth/login", json={"email": "operador@exemplo.com", "senha": _SENHA}
    )
    assert resposta.status_code == 200
    assert resposta.json()["usuario"]["papel"] == "gerente"
    assert client.get("/api/auth/me").json()["usuario"]["papel"] == "gerente"
