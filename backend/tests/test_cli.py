"""Testes da gestão de contas pela linha de comando."""

from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from src import cli
from src.config.settings import Settings
from src.repositories import UsuarioRepository
from src.services.senhas import ServicoDeSenhas
from src.services.sessoes import ServicoDeSessoes

_AGORA = datetime(2026, 3, 21, 12, tzinfo=timezone.utc)
_SENHA = "uma frase longa e bem diferente 2026"


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    for nome, valor in {
        "DATABASE_URL": "postgresql://db-ficticio:5432/armadilhas",
        "MODEL_WEIGHTS_PATH": "/caminho-ficticio/pesos.pt",
        "MODEL_VERSION": "v0.1.0-dev",
        "INFERENCE_MODE": "stub",
        "UPLOADS_DIR": "/tmp/uploads",
        "CORS_ORIGENS": "http://localhost:5173",
    }.items():
        monkeypatch.setenv(nome, valor)
    return Settings()


@pytest.fixture(scope="module")
def senhas() -> ServicoDeSenhas:
    return ServicoDeSenhas(memoria_kib=19456, iteracoes=2, paralelismo=1)


def _criar(session: Session, senhas: ServicoDeSenhas, email: str = "Ana@Exemplo.com"):
    return cli.criar_usuario(
        session, senhas, email=email, nome="Ana Lima", senha=_SENHA
    )


def test_criar_usuario_normaliza_email_e_guarda_hash(
    session: Session, senhas: ServicoDeSenhas
) -> None:
    usuario = _criar(session, senhas)

    assert usuario.email == "ana@exemplo.com"
    assert usuario.ativo is True
    assert usuario.senha_hash.startswith("$argon2id$")
    assert _SENHA not in usuario.senha_hash


def test_criar_usuario_recusa_senha_fraca_e_email_repetido(
    session: Session, senhas: ServicoDeSenhas
) -> None:
    _criar(session, senhas)

    with pytest.raises(cli.ErroDeComando, match="15 caracteres"):
        cli.criar_usuario(
            session, senhas, email="b@exemplo.com", nome="B Souza", senha="curta"
        )
    with pytest.raises(cli.ErroDeComando, match="Já existe"):
        _criar(session, senhas, email="ana@exemplo.com")


def test_redefinir_senha_encerra_sessoes_e_desbloqueia(
    session: Session, settings: Settings, senhas: ServicoDeSenhas
) -> None:
    usuario = _criar(session, senhas)
    UsuarioRepository(session).definir_bloqueio(usuario, _AGORA.replace(year=2027))
    sessao, token = ServicoDeSessoes(session, settings).criar(
        usuario, agora=_AGORA, ip=None, user_agent=None
    )

    cli.redefinir_senha(
        session,
        settings,
        senhas,
        email="ANA@exemplo.com",
        senha="outra frase igualmente longa 2027",
        agora=_AGORA,
    )

    session.refresh(sessao)
    assert usuario.bloqueado_ate is None
    assert sessao.revogada_em == _AGORA
    assert senhas.verificar("outra frase igualmente longa 2027", usuario.senha_hash)[0]


def test_desativar_encerra_sessoes_e_ativar_reabre_a_conta(
    session: Session, settings: Settings, senhas: ServicoDeSenhas
) -> None:
    usuario = _criar(session, senhas)
    sessao, _ = ServicoDeSessoes(session, settings).criar(
        usuario, agora=_AGORA, ip=None, user_agent=None
    )

    cli.alterar_ativo(
        session, settings, email="ana@exemplo.com", ativo=False, agora=_AGORA
    )
    session.refresh(sessao)
    assert usuario.ativo is False and sessao.revogada_em == _AGORA

    cli.alterar_ativo(
        session, settings, email="ana@exemplo.com", ativo=True, agora=_AGORA
    )
    assert usuario.ativo is True


def test_comandos_sobre_conta_inexistente_falham(
    session: Session, settings: Settings
) -> None:
    with pytest.raises(cli.ErroDeComando, match="não encontrada"):
        cli.desbloquear(session, email="ninguem@exemplo.com")
    with pytest.raises(cli.ErroDeComando, match="não encontrada"):
        cli.alterar_ativo(
            session, settings, email="ninguem@exemplo.com", ativo=False, agora=_AGORA
        )


def test_listagem_nao_expoe_dados_de_senha(
    session: Session, senhas: ServicoDeSenhas
) -> None:
    _criar(session, senhas)

    linhas = cli.listar(session)

    assert linhas == ["ana@exemplo.com\tAna Lima\tativa"]
