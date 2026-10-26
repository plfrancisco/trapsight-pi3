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
from src.services.limitador_contas import LimitadorDeContas
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
    assert criado.troca_senha_pendente is True
    lista = client.get("/api/usuarios")
    assert lista.status_code == 200
    assert lista.headers["Cache-Control"] == "no-store"
    assert [item["email"] for item in lista.json()] == sorted(
        item["email"] for item in lista.json()
    )
    assert _SENHA not in resposta.text + lista.text + caplog.text
    assert "senha_hash" not in resposta.text + lista.text + caplog.text
    assert criado.senha_hash not in resposta.text + lista.text + caplog.text
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


def test_criacao_de_contas_respeita_limite_por_gerente_e_janela(client, session):
    """Cada gerente recupera sua própria cota quando a janela de uma hora fecha."""
    agora = [0.0]
    client.app.state.limitador_de_contas = LimitadorDeContas(
        1, relogio=lambda: agora[0]
    )
    primeiro_gerente = _autenticar(client, session)

    assert client.post("/api/usuarios", json=_CORPO).status_code == 201
    bloqueada = client.post(
        "/api/usuarios", json={**_CORPO, "email": "bloqueada@exemplo.com"}
    )
    assert bloqueada.status_code == 429
    assert bloqueada.json()["erro"]["codigo"] == "LIMITE_CONTAS"
    assert bloqueada.headers["Retry-After"] == "3601"

    session.execute(
        update(Usuario)
        .where(Usuario.id == primeiro_gerente.id)
        .values(papel=PapelUsuario.OPERADOR),
        execution_options={"synchronize_session": False},
    )
    segundo_gerente = criar_usuario(
        session,
        client.app,
        email="gerente-2@exemplo.com",
        papel=PapelUsuario.GERENTE,
    )
    aplicar_credenciais(client, criar_sessao(session, client.app, segundo_gerente))
    assert (
        client.post(
            "/api/usuarios", json={**_CORPO, "email": "outro-gerente@exemplo.com"}
        ).status_code
        == 201
    )

    agora[0] = 3600.0
    aplicar_credenciais(client, criar_sessao(session, client.app, primeiro_gerente))
    assert (
        client.post(
            "/api/usuarios", json={**_CORPO, "email": "janela-aberta@exemplo.com"}
        ).status_code
        == 403
    )
    session.execute(
        update(Usuario)
        .where(Usuario.id == segundo_gerente.id)
        .values(papel=PapelUsuario.OPERADOR),
        execution_options={"synchronize_session": False},
    )
    session.execute(
        update(Usuario)
        .where(Usuario.id == primeiro_gerente.id)
        .values(papel=PapelUsuario.GERENTE),
        execution_options={"synchronize_session": False},
    )
    assert (
        client.post(
            "/api/usuarios", json={**_CORPO, "email": "janela-aberta@exemplo.com"}
        ).status_code
        == 201
    )


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


@pytest.mark.parametrize(
    "metodo,caminho",
    [
        ("GET", "/api/armadilhas"),
        ("GET", "/api/usuarios"),
        ("GET", "/api/analises/00000000-0000-0000-0000-000000000000/imagem"),
        ("POST", "/api/armadilhas"),
        ("DELETE", "/api/rota-futura"),
        ("GET", "/api/auth/me/"),
    ],
)
def test_troca_pendente_restringe_rotas_globalmente(client, session, metodo, caminho):
    usuario = _autenticar(client, session)
    session.execute(
        update(Usuario)
        .where(Usuario.id == usuario.id)
        .values(troca_senha_pendente=True),
        execution_options={"synchronize_session": False},
    )
    resposta = client.request(metodo, caminho)
    assert resposta.status_code == 403
    assert resposta.json()["erro"]["codigo"] == "TROCA_DE_SENHA_OBRIGATORIA"
    assert resposta.headers["Cache-Control"] == "no-store"
    assert client.get("/api/auth/me").json()["usuario"]["troca_senha_pendente"] is True


def test_operador_novo_so_acessa_dados_apos_trocar_senha(client, session):
    _autenticar(client, session)
    assert client.post("/api/usuarios", json=_CORPO).status_code == 201
    usuario = session.scalars(
        select(Usuario).where(Usuario.email == _CORPO["email"])
    ).one()
    outra = criar_sessao(session, client.app, usuario)
    client.cookies.clear()
    login = client.post(
        "/api/auth/login", json={"email": usuario.email, "senha": _SENHA}
    )
    assert login.status_code == 200
    assert login.json()["usuario"]["troca_senha_pendente"] is True
    assert login.json()["usuario"]["papel"] == "operador"
    token_antigo = client.cookies.get("trapsight_sessao")
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    assert client.get("/api/armadilhas").status_code == 403
    troca = client.post(
        "/api/auth/senha",
        json={
            "senha_atual": _SENHA,
            "senha_nova": "outra frase igualmente longa 2027",
        },
    )
    assert troca.status_code == 200
    assert client.get("/api/auth/me").json()["usuario"]["troca_senha_pendente"] is False
    assert client.get("/api/armadilhas").status_code == 200
    for token in (token_antigo, outra.token):
        resposta = client.get(
            "/api/auth/me", headers={"Cookie": f"trapsight_sessao={token}"}
        )
        assert resposta.status_code == 401
    session.refresh(usuario)
    assert usuario.troca_senha_pendente is False
    assert (
        session.scalar(
            select(func.count())
            .select_from(Sessao)
            .where(Sessao.usuario_id == usuario.id, Sessao.revogada_em.is_not(None))
        )
        == 2
    )


@pytest.mark.parametrize(
    "senha_atual,senha_nova,status",
    [
        ("incorreta", "outra frase igualmente longa 2027", 401),
        (_SENHA, "curta", 422),
    ],
)
def test_troca_recusada_mantem_pendencia(
    client, session, senha_atual, senha_nova, status
):
    usuario = _autenticar(client, session)
    usuario.troca_senha_pendente = True
    session.flush()
    resposta = client.post(
        "/api/auth/senha",
        json={
            "senha_atual": senha_atual,
            "senha_nova": senha_nova,
        },
    )
    assert resposta.status_code == status
    session.refresh(usuario)
    assert usuario.troca_senha_pendente is True
    assert (
        client.get("/api/usuarios").json()["erro"]["codigo"]
        == "TROCA_DE_SENHA_OBRIGATORIA"
    )


def test_pendencia_permite_logout_mas_nao_dispensa_csrf(client, session):
    usuario = _autenticar(client, session)
    usuario.troca_senha_pendente = True
    session.flush()
    token_csrf = client.headers.pop("X-CSRF-Token")
    assert client.post("/api/auth/logout").json()["erro"]["codigo"] == "CSRF_INVALIDO"
    client.headers["X-CSRF-Token"] = token_csrf
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401
