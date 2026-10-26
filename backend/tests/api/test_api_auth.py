"""Testes de login, sessão, CSRF, bloqueios e troca de senha da API."""

from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.dependencias import get_session
from src.entities import Sessao, TentativaLogin, Usuario
from tests.auth_helpers import (
    EMAIL_DE_TESTE,
    ORIGEM_DE_TESTE,
    SENHA_DE_TESTE,
    aplicar_credenciais,
    criar_sessao,
    criar_usuario,
)

_INICIO = datetime(2026, 3, 21, 12, tzinfo=timezone.utc)
_AMBIENTE_FICTICIO = {
    "DATABASE_URL": "postgresql://db-ficticio:5432/armadilhas",
    "MODEL_WEIGHTS_PATH": "/caminho-ficticio/pesos.pt",
    "MODEL_VERSION": "v0.1.0-dev",
    "INFERENCE_MODE": "stub",
    "CORS_ORIGENS": ORIGEM_DE_TESTE,
    "ARGON2_MEMORIA_KIB": "19456",
    "ARGON2_ITERACOES": "2",
}
_SENHA_NOVA = "outra frase igualmente longa 2027"


class Relogio:
    """Relógio controlável, injetado em `app.state.relogio`."""

    def __init__(self) -> None:
        self.agora = _INICIO

    def __call__(self) -> datetime:
        return self.agora

    def avancar(self, **intervalo: float) -> None:
        self.agora += timedelta(**intervalo)


@pytest.fixture
def relogio() -> Relogio:
    return Relogio()


@pytest.fixture
def client(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    relogio: Relogio,
) -> TestClient:
    """Cliente sem sessão: cada teste faz o próprio login."""
    for nome, valor in _AMBIENTE_FICTICIO.items():
        monkeypatch.setenv(nome, valor)
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path / "uploads"))

    from src.main import create_app

    app = create_app()

    def substituir_sessao():
        yield session

    app.dependency_overrides[get_session] = substituir_sessao
    app.state.relogio = relogio
    app.state.provedor_de_sessao = lambda: nullcontext(session)
    with TestClient(app) as test_client:
        test_client.headers["Origin"] = ORIGEM_DE_TESTE
        yield test_client
    app.dependency_overrides.clear()


def _entrar(
    client: TestClient, email: str = EMAIL_DE_TESTE, senha: str = SENHA_DE_TESTE
):
    return client.post("/api/auth/login", json={"email": email, "senha": senha})


def _logar(client: TestClient, session: Session) -> dict:
    criar_usuario(session, client.app)
    resposta = _entrar(client)
    assert resposta.status_code == 200
    client.headers["X-CSRF-Token"] = resposta.json()["csrf_token"]
    return resposta.json()


def test_aplicar_credenciais_substitui_sessao_de_login(
    client: TestClient, session: Session
) -> None:
    """Aplica outra sessão sem manter o cookie recebido no login anterior."""
    _logar(client, session)
    usuario = criar_usuario(session, client.app, email="outra@exemplo.com")
    credenciais = criar_sessao(session, client.app, usuario)

    aplicar_credenciais(client, credenciais)
    resposta = client.get("/api/auth/me")

    assert resposta.status_code == 200
    assert resposta.json()["usuario"]["email"] == usuario.email
    assert resposta.json()["csrf_token"] == credenciais.csrf_token
    assert len(list(client.cookies.jar)) == 1
    assert client.headers["X-CSRF-Token"] == credenciais.csrf_token
    assert client.headers["Origin"] == ORIGEM_DE_TESTE


def test_login_valido_abre_sessao_com_cookie_restrito(
    client: TestClient, session: Session
) -> None:
    criar_usuario(session, client.app)

    resposta = _entrar(client)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["usuario"]["email"] == EMAIL_DE_TESTE
    assert "senha" not in corpo and "senha" not in corpo["usuario"]
    assert "senha_hash" not in resposta.text
    assert SENHA_DE_TESTE not in resposta.text
    cookie = resposta.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert "path=/" in cookie
    assert "max-age" not in cookie and "expires" not in cookie
    assert "domain" not in cookie
    assert "secure" not in cookie  # desenvolvimento local, sem HTTPS


def test_banco_guarda_so_o_hash_do_token(client: TestClient, session: Session) -> None:
    criar_usuario(session, client.app)
    resposta = _entrar(client)
    token = client.cookies.get("trapsight_sessao")

    sessoes = list(session.scalars(select(Sessao)))

    assert token and resposta.status_code == 200
    assert len(sessoes) == 1
    assert sessoes[0].token_hash != token
    assert len(sessoes[0].token_hash) == 64


def test_cookie_de_producao_usa_prefixo_host_e_secure(
    session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, relogio: Relogio
) -> None:
    for nome, valor in _AMBIENTE_FICTICIO.items():
        monkeypatch.setenv(nome, valor)
    monkeypatch.setenv("CORS_ORIGENS", "https://app.exemplo.com")
    monkeypatch.setenv("AMBIENTE", "producao")
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path / "uploads"))
    from src.main import create_app

    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.state.relogio = relogio
    app.state.provedor_de_sessao = lambda: nullcontext(session)
    criar_usuario(session, app)
    with TestClient(app, base_url="https://app.exemplo.com") as cliente:
        resposta = cliente.post(
            "/api/auth/login",
            json={"email": EMAIL_DE_TESTE, "senha": SENHA_DE_TESTE},
            headers={"Origin": "https://app.exemplo.com"},
        )
        docs = cliente.get("/docs")
        openapi = cliente.get("/openapi.json")

    cookie = resposta.headers["set-cookie"]
    assert cookie.startswith("__Host-trapsight_sessao=")
    assert "Secure" in cookie and "HttpOnly" in cookie
    assert docs.status_code == 404
    assert openapi.status_code == 404


def test_falhas_de_login_sao_indistinguiveis(
    client: TestClient, session: Session
) -> None:
    criar_usuario(session, client.app)
    inativo = criar_usuario(session, client.app, email="inativo@exemplo.com")
    inativo.ativo = False
    session.flush()

    respostas = [
        _entrar(client, senha="senha errada completamente diferente"),
        _entrar(client, email="ninguem@exemplo.com"),
        _entrar(client, email="inativo@exemplo.com"),
    ]

    assert {r.status_code for r in respostas} == {401}
    assert len({r.text for r in respostas}) == 1
    assert respostas[0].json()["erro"]["codigo"] == "CREDENCIAIS_INVALIDAS"
    assert all("set-cookie" not in r.headers for r in respostas)


def test_email_e_normalizado_no_login(client: TestClient, session: Session) -> None:
    criar_usuario(session, client.app)

    assert _entrar(client, email="  OPERADOR@Exemplo.com ").status_code == 200


def test_conta_bloqueia_apos_cinco_falhas_mesmo_com_senha_certa(
    client: TestClient, session: Session, relogio: Relogio
) -> None:
    criar_usuario(session, client.app)
    for _ in range(5):
        assert _entrar(client, senha="errada errada errada errada").status_code == 401

    bloqueada = _entrar(client)
    relogio.avancar(minutes=16)
    liberada = _entrar(client)

    assert bloqueada.status_code == 401
    assert bloqueada.json()["erro"]["codigo"] == "CREDENCIAIS_INVALIDAS"
    assert liberada.status_code == 200


def test_falhar_durante_o_bloqueio_nao_o_estende(
    client: TestClient, session: Session, relogio: Relogio
) -> None:
    criar_usuario(session, client.app)
    for _ in range(5):
        _entrar(client, senha="errada errada errada errada")
    relogio.avancar(minutes=10)
    for _ in range(3):
        _entrar(client, senha="errada errada errada errada")
    relogio.avancar(minutes=6)  # 16 min desde o bloqueio

    assert _entrar(client).status_code == 200


def test_ip_com_muitas_falhas_recebe_429_com_retry_after(
    client: TestClient, session: Session
) -> None:
    for indice in range(30):
        _entrar(client, email=f"alvo{indice}@exemplo.com")

    resposta = _entrar(client, email="outro@exemplo.com")

    assert resposta.status_code == 429
    assert resposta.json()["erro"]["codigo"] == "LIMITE_TENTATIVAS"
    assert int(resposta.headers["retry-after"]) > 0


def test_tentativa_nao_grava_email_nem_senha(
    client: TestClient, session: Session
) -> None:
    _entrar(client, email="alguem@exemplo.com", senha="errada errada errada errada")

    tentativas = list(session.scalars(select(TentativaLogin)))

    assert len(tentativas) == 1
    texto = repr([vars(t) for t in tentativas])
    assert "alguem@exemplo.com" not in texto
    assert "errada" not in texto


def test_login_exige_origem_permitida(client: TestClient, session: Session) -> None:
    criar_usuario(session, client.app)

    hostil = client.post(
        "/api/auth/login",
        json={"email": EMAIL_DE_TESTE, "senha": SENHA_DE_TESTE},
        headers={"Origin": "https://hostil.example"},
    )

    assert hostil.status_code == 403
    assert hostil.json()["erro"]["codigo"] == "CSRF_INVALIDO"


def test_caractere_nulo_no_login_e_recusado_sem_erro_de_servidor(
    client: TestClient,
) -> None:
    resposta = client.post(
        "/api/auth/login", json={"email": "a@b.co\u0000", "senha": "x\u0000y"}
    )

    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "VALIDACAO_FALHOU"


@pytest.mark.parametrize("campo", ["identificador", "localizacao"])
def test_caractere_nulo_nos_textos_da_armadilha_e_recusado(
    client: TestClient, session: Session, campo: str
) -> None:
    _logar(client, session)
    corpo = {"identificador": "ARM-001", campo: "valor\u0000nulo"}

    resposta = client.post("/api/armadilhas", json=corpo)

    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "VALIDACAO_FALHOU"


def test_rota_protegida_sem_sessao_devolve_401(client: TestClient) -> None:
    resposta = client.get("/api/armadilhas")

    assert resposta.status_code == 401
    assert resposta.json()["erro"]["codigo"] == "NAO_AUTENTICADO"
    assert resposta.headers["cache-control"] == "no-store"


def test_todas_as_rotas_da_api_exigem_sessao(client: TestClient) -> None:
    caminhos = client.app.openapi()["paths"]
    verificadas = 0
    for caminho, metodos in caminhos.items():
        if caminho == "/api/auth/login":
            continue
        for metodo in metodos:
            url = caminho.replace("{", "").replace("}", "")
            url = url.replace("armadilha_id", "00000000-0000-0000-0000-000000000000")
            resposta = client.request(metodo.upper(), url)
            assert resposta.status_code == 401, f"{metodo.upper()} {caminho}"
            verificadas += 1
    assert verificadas >= 8


def test_me_devolve_usuario_e_csrf(client: TestClient, session: Session) -> None:
    sessao = _logar(client, session)

    resposta = client.get("/api/auth/me")

    assert resposta.status_code == 200
    assert resposta.json()["csrf_token"] == sessao["csrf_token"]
    assert resposta.json()["usuario"]["email"] == EMAIL_DE_TESTE


@pytest.mark.parametrize(
    "cabecalhos",
    [
        {"X-CSRF-Token": ""},
        {"X-CSRF-Token": "token-errado"},
        {"Origin": "https://hostil.example"},
    ],
    ids=["csrf-vazio", "csrf-errado", "origem-hostil"],
)
def test_metodo_que_altera_estado_exige_csrf_e_origem(
    client: TestClient, session: Session, cabecalhos: dict[str, str]
) -> None:
    _logar(client, session)

    resposta = client.post("/api/auth/logout", headers=cabecalhos)

    assert resposta.status_code == 403
    assert resposta.json()["erro"]["codigo"] == "CSRF_INVALIDO"
    assert client.get("/api/auth/me").status_code == 200


def test_requisicao_sem_origem_nem_referer_e_recusada(
    client: TestClient, session: Session
) -> None:
    _logar(client, session)
    del client.headers["Origin"]

    assert client.post("/api/auth/logout").status_code == 403


def test_logout_revoga_a_sessao_no_servidor(
    client: TestClient, session: Session
) -> None:
    _logar(client, session)
    token = client.cookies.get("trapsight_sessao")

    saida = client.post("/api/auth/logout")
    client.cookies.set("trapsight_sessao", token)  # token roubado reapresentado
    depois = client.get("/api/auth/me")

    assert saida.status_code == 204
    assert depois.status_code == 401


def test_sessao_expira_por_inatividade(
    client: TestClient, session: Session, relogio: Relogio
) -> None:
    _logar(client, session)

    relogio.avancar(minutes=31)

    assert client.get("/api/auth/me").status_code == 401


def test_atividade_renova_a_inatividade_mas_nao_o_prazo_absoluto(
    client: TestClient, session: Session, relogio: Relogio
) -> None:
    _logar(client, session)
    for _ in range(18):  # 9 h de uso contínuo, uma requisição a cada 30 min
        relogio.avancar(minutes=29)
        resposta = client.get("/api/auth/me")
        if resposta.status_code == 401:
            break

    assert resposta.status_code == 401
    assert relogio.agora - _INICIO <= timedelta(hours=8, minutes=30)


def test_limite_de_sessoes_revoga_a_mais_antiga(
    client: TestClient, session: Session, relogio: Relogio
) -> None:
    usuario = criar_usuario(session, client.app)
    abertas = []
    for _ in range(6):
        relogio.avancar(seconds=1)
        abertas.append(criar_sessao(session, client.app, usuario))

    aplicar_credenciais(client, abertas[0])
    primeira = client.get("/api/auth/me")
    aplicar_credenciais(client, abertas[-1])
    ultima = client.get("/api/auth/me")

    assert primeira.status_code == 401
    assert ultima.status_code == 200


def test_conta_desativada_perde_a_sessao(client: TestClient, session: Session) -> None:
    _logar(client, session)
    session.scalars(select(Usuario)).one().ativo = False
    session.flush()

    assert client.get("/api/auth/me").status_code == 401


def test_troca_de_senha_revoga_outras_sessoes_e_emite_nova(
    client: TestClient, session: Session
) -> None:
    _logar(client, session)
    outra = criar_sessao(session, client.app, session.scalars(select(Usuario)).one())
    token_antigo = client.cookies.get("trapsight_sessao")

    resposta = client.post(
        "/api/auth/senha",
        json={"senha_atual": SENHA_DE_TESTE, "senha_nova": _SENHA_NOVA},
    )

    assert resposta.status_code == 200
    novo = client.cookies.get("trapsight_sessao")
    assert novo != token_antigo
    client.headers["X-CSRF-Token"] = resposta.json()["csrf_token"]
    assert client.get("/api/auth/me").status_code == 200
    client.cookies.clear()
    client.cookies.set("trapsight_sessao", outra.token)
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.set("trapsight_sessao", token_antigo)
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.clear()
    assert _entrar(client, senha=SENHA_DE_TESTE).status_code == 401
    assert _entrar(client, senha=_SENHA_NOVA).status_code == 200


def test_troca_de_senha_exige_a_senha_atual(
    client: TestClient, session: Session
) -> None:
    _logar(client, session)

    resposta = client.post(
        "/api/auth/senha",
        json={
            "senha_atual": "senha atual errada de verdade",
            "senha_nova": _SENHA_NOVA,
        },
    )

    assert resposta.status_code == 401
    assert resposta.json()["erro"]["codigo"] == "CREDENCIAIS_INVALIDAS"


@pytest.mark.parametrize("pendente", [False, True])
def test_troca_recusa_reutilizar_senha_atual(
    client: TestClient, session: Session, pendente: bool
) -> None:
    """A mesma senha não pode satisfazer a troca inicial nem uma troca comum."""
    _logar(client, session)
    usuario = session.scalars(select(Usuario)).one()
    usuario.troca_senha_pendente = pendente
    session.flush()

    resposta = client.post(
        "/api/auth/senha",
        json={"senha_atual": SENHA_DE_TESTE, "senha_nova": SENHA_DE_TESTE},
    )

    assert resposta.status_code == 422
    assert resposta.json()["erro"] == {
        "codigo": "SENHA_FRACA",
        "mensagem": "A nova senha não atende à política de senhas.",
        "detalhes": {"motivo": "igual_atual"},
    }
    session.refresh(usuario)
    assert usuario.troca_senha_pendente is pendente
    assert _entrar(client, senha=SENHA_DE_TESTE).status_code == 200


def test_troca_reutilizada_audita_motivo_sem_dados_sensiveis(
    client: TestClient, session: Session, capfd
) -> None:
    """A recusa da senha repetida deixa rastro sem registrar credenciais."""
    _logar(client, session)
    from src.services.auditoria import configurar_auditoria

    configurar_auditoria()

    resposta = client.post(
        "/api/auth/senha",
        json={"senha_atual": SENHA_DE_TESTE, "senha_nova": SENHA_DE_TESTE},
    )

    saida, _ = capfd.readouterr()
    assert resposta.status_code == 422
    assert "auth.troca_senha_recusada" in saida
    assert "motivo=igual_atual" in saida
    assert SENHA_DE_TESTE not in saida


@pytest.mark.parametrize(
    ("senha_nova", "motivo"),
    [
        ("curta demais", "curta"),
        ("a" * 129, "longa"),
        ("password1234567", "comum"),
        ("defghijklmnopqrs", "trivial"),
        ("operador-12345-xyz", "contextual"),
    ],
)
def test_senha_nova_fraca_e_recusada_sem_ecoar_a_senha(
    client: TestClient, session: Session, senha_nova: str, motivo: str
) -> None:
    _logar(client, session)

    resposta = client.post(
        "/api/auth/senha",
        json={"senha_atual": SENHA_DE_TESTE, "senha_nova": senha_nova},
    )

    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "SENHA_FRACA"
    assert resposta.json()["erro"]["detalhes"]["motivo"] == motivo
    assert senha_nova not in resposta.text
    assert client.get("/api/auth/me").status_code == 200


def test_cabecalhos_de_seguranca_e_sem_cache_nas_rotas_de_auth(
    client: TestClient, session: Session
) -> None:
    _logar(client, session)

    resposta = client.get("/api/auth/me")

    assert resposta.headers["x-content-type-options"] == "nosniff"
    assert resposta.headers["cache-control"] == "no-store"
    assert "server" not in resposta.headers
