"""Testes PostgreSQL para a auditoria durável das ações administrativas."""

import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, insert, select, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from src import cli
from src.config.database import create_session_factory
from src.config.settings import Settings
from src.entities import AuditoriaCLI, Usuario
from src.repositories import UsuarioRepository
from src.services.senhas import ServicoDeSenhas

_SENHA_INICIAL = "uma frase longa e bem diferente 2026"
_SENHA_NOVA = "outra frase igualmente longa 2027"
_AGORA = datetime(2026, 10, 28, 12, tzinfo=timezone.utc)


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    for nome, valor in {
        "DATABASE_URL": "postgresql://db-ficticio:5432/armadilhas",
        "MODEL_WEIGHTS_PATH": "/tmp/pesos.pt",
        "MODEL_VERSION": "v0.1.0-test",
        "INFERENCE_MODE": "stub",
        "UPLOADS_DIR": "/tmp/uploads",
        "CORS_ORIGENS": "http://localhost:5173",
    }.items():
        monkeypatch.setenv(nome, valor)
    return Settings()


@pytest.fixture(scope="module")
def senhas() -> ServicoDeSenhas:
    return ServicoDeSenhas(memoria_kib=19456, iteracoes=2, paralelismo=1)


def _auditar(
    session: Session,
    args: argparse.Namespace,
    settings: Settings,
    senhas: ServicoDeSenhas,
    monkeypatch: pytest.MonkeyPatch,
    senha: str = _SENHA_INICIAL,
) -> list[str]:
    monkeypatch.setattr(cli, "_ler_senha", lambda _stdin: senha)
    return cli._executar_com_auditoria(args, session, settings, senhas, _AGORA)


def test_cli_persiste_sucesso_para_as_seis_acoes(
    session: Session,
    settings: Settings,
    senhas: ServicoDeSenhas,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args = cli._parser().parse_args(
        [
            "criar-usuario",
            "--email",
            "auditado@exemplo.com",
            "--nome",
            "Conta Auditada",
        ]
    )
    _auditar(session, args, settings, senhas, monkeypatch)
    usuario = UsuarioRepository(session).get_by_email("auditado@exemplo.com")
    assert usuario is not None

    comandos = [
        ["definir-papel", "--email", usuario.email, "--papel", "gerente"],
        ["redefinir-senha", "--email", usuario.email],
        ["ativar-usuario", "--email", usuario.email],
        ["desativar-usuario", "--email", usuario.email],
        ["desbloquear-usuario", "--email", usuario.email],
    ]
    for comando in comandos:
        args = cli._parser().parse_args(comando)
        senha = _SENHA_NOVA if args.comando == "redefinir-senha" else _SENHA_INICIAL
        _auditar(session, args, settings, senhas, monkeypatch, senha)

    registros = session.scalars(
        select(AuditoriaCLI)
        .where(AuditoriaCLI.conta_alvo == usuario.id)
        .order_by(AuditoriaCLI.ocorrido_em, AuditoriaCLI.evento)
    ).all()
    assert {registro.evento for registro in registros} == {
        "criar-usuario",
        "definir-papel",
        "redefinir-senha",
        "ativar-usuario",
        "desativar-usuario",
        "desbloquear-usuario",
    }
    assert all(registro.resultado == "sucesso" for registro in registros)
    assert all(registro.executor for registro in registros)
    assert all(registro.ocorrido_em.tzinfo is not None for registro in registros)

    credencial = next(r for r in registros if r.evento == "redefinir-senha")
    campos = " ".join(
        str(getattr(credencial, nome))
        for nome in (
            "evento",
            "executor",
            "conta_alvo",
            "resultado",
            "detalhe",
        )
    )
    assert _SENHA_NOVA not in campos
    assert usuario.senha_hash not in campos
    assert "token" not in campos.lower()
    assert "hash" not in campos.lower()


def test_main_despacha_criacao_pela_auditoria_duravel(
    engine: Engine,
    check_database_revision: None,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli, "Settings", lambda: settings)
    monkeypatch.setattr(cli, "_ler_senha", lambda _stdin: _SENHA_INICIAL)
    monkeypatch.setattr(cli, "create_database_engine", lambda _url: engine)
    fabrica = create_session_factory(engine)
    email = f"duravel-{uuid4()}@exemplo.com"
    conta_id: UUID | None = None

    try:
        assert (
            cli.main(["criar-usuario", "--email", email, "--nome", "Despacho CLI"]) == 0
        )

        with fabrica() as verification:
            usuario = UsuarioRepository(verification).get_by_email(email)
            assert usuario is not None
            conta_id = usuario.id
            registro = verification.scalar(
                select(AuditoriaCLI).where(
                    AuditoriaCLI.evento == "criar-usuario",
                    AuditoriaCLI.conta_alvo == usuario.id,
                )
            )
            assert registro is not None
            assert registro.resultado == "sucesso"
    finally:
        with fabrica() as cleanup:
            if conta_id is None:
                usuario = UsuarioRepository(cleanup).get_by_email(email)
                conta_id = usuario.id if usuario is not None else None
            if conta_id is not None:
                cleanup.execute(
                    delete(AuditoriaCLI).where(AuditoriaCLI.conta_alvo == conta_id)
                )
                cleanup.execute(delete(Usuario).where(Usuario.id == conta_id))
                cleanup.commit()


def test_falha_da_cli_tambem_fica_gravada_sem_email_digitado(
    session: Session,
    settings: Settings,
    senhas: ServicoDeSenhas,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    email = "frase-secreta@nao-existe.example"
    args = cli._parser().parse_args(["desativar-usuario", "--email", email])

    with pytest.raises(cli.ErroDeComando, match="não encontrada"):
        _auditar(session, args, settings, senhas, monkeypatch)

    registro = session.scalar(
        select(AuditoriaCLI).where(
            AuditoriaCLI.evento == "desativar-usuario",
            AuditoriaCLI.resultado == "falha",
        )
    )
    assert registro is not None
    assert registro.conta_alvo is None
    assert registro.detalhe == "comando rejeitado"
    campos = " ".join(
        str(getattr(registro, nome))
        for nome in ("evento", "executor", "conta_alvo", "resultado", "detalhe")
    )
    assert email not in campos


def test_papeis_execucao_podem_inserir_e_consultar_mas_nao_editar_ou_apagar(
    session: Session,
) -> None:
    papeis = session.scalars(
        text(
            "SELECT rolname FROM pg_roles "
            "WHERE rolname IN ('trapsight_runtime', 'trapsight_app') "
            "ORDER BY rolname"
        )
    ).all()
    assert "trapsight_runtime" in papeis

    for papel in papeis:
        with session.begin_nested():
            session.execute(text(f"SET LOCAL ROLE {papel}"))
            session.execute(
                insert(AuditoriaCLI).values(
                    ocorrido_em=datetime.now(timezone.utc),
                    evento="desbloquear-usuario",
                    executor="teste-postgres",
                    conta_alvo=None,
                    resultado="sucesso",
                    detalhe="bloqueio removido",
                )
            )
            assert session.scalar(select(AuditoriaCLI.id).limit(1)) is not None

        with pytest.raises(DBAPIError):
            with session.begin_nested():
                session.execute(text(f"SET LOCAL ROLE {papel}"))
                session.execute(update(AuditoriaCLI).values(detalhe="alterado"))

        with pytest.raises(DBAPIError):
            with session.begin_nested():
                session.execute(text(f"SET LOCAL ROLE {papel}"))
                session.execute(delete(AuditoriaCLI))


def test_cli_interrompe_a_acao_quando_nao_consegue_gravar_auditoria(
    session: Session,
    settings: Settings,
    senhas: ServicoDeSenhas,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    usuario = cli.criar_usuario(
        session,
        senhas,
        email="conta-offline@exemplo.com",
        nome="Sem Auditoria",
        senha=_SENHA_INICIAL,
    )
    session.commit()

    class AuditoriaIndisponivel:
        def __init__(self, _session: Session) -> None:
            pass

        def registrar(self, **_campos: object) -> None:
            raise RuntimeError("banco indisponível")

    monkeypatch.setattr(cli, "AuditoriaCLIRepository", AuditoriaIndisponivel)
    monkeypatch.setattr(cli, "Settings", lambda: settings)
    engine = MagicMock()
    monkeypatch.setattr(cli, "create_database_engine", lambda _url: engine)
    monkeypatch.setattr(
        cli,
        "create_session_factory",
        lambda _engine: lambda: nullcontext(session),
    )

    codigo = cli.main(["desativar-usuario", "--email", usuario.email])
    saida, erro = capfd.readouterr()

    session.refresh(usuario)
    assert codigo == 1
    assert "auditoria no banco; comando cancelado" in erro
    assert saida == ""
    assert usuario.ativo is True
