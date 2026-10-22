"""Verifica a leitura segura da configuração de conexão."""

import pytest
from sqlalchemy import create_engine

from src.config.database import (
    DatabaseConfigurationError,
    create_database_engine,
    create_session_factory,
    database_url_from_environment,
)


def test_engine_uses_psycopg_driver_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Converte URLs PostgreSQL padrão ao driver Psycopg sem abrir conexão."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://db:5432/armadilhas")
    engine = create_database_engine()
    try:
        assert engine.url.drivername == "postgresql+psycopg"
    finally:
        engine.dispose()


def test_engine_accepts_url_validada_sem_ler_ambiente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cria o engine com URL recebida sem abrir conexão nem consultar o ambiente."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    engine = create_database_engine("postgresql://db:5432/armadilhas")
    try:
        assert engine.url.drivername == "postgresql+psycopg"
        assert engine.pool.checkedout() == 0
    finally:
        engine.dispose()


def test_database_url_helper_returns_psycopg_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compartilha a mesma conversão PostgreSQL usada pelo Alembic e pelo engine."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://db:5432/armadilhas")

    url = database_url_from_environment()

    assert url.drivername == "postgresql+psycopg"


def test_missing_database_url_has_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Falha com mensagem útil quando a variável não foi configurada."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(DatabaseConfigurationError, match="DATABASE_URL não definida"):
        create_database_engine()


def test_invalid_database_url_does_not_leak_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Oculta o valor inválido ao informar que a configuração precisa de correção."""
    invalid_url = "postgresql://db:PORTA_INVALIDA/armadilhas"
    monkeypatch.setenv("DATABASE_URL", invalid_url)
    with pytest.raises(DatabaseConfigurationError) as captured:
        create_database_engine()
    assert "DATABASE_URL inválida" in str(captured.value)
    assert invalid_url not in str(captured.value)


def test_session_factory_requires_and_uses_the_given_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vincula as sessões ao engine explícito sem ler configuração adicional."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    engine = create_engine("postgresql+psycopg://")
    try:
        session_factory = create_session_factory(engine)
        session = session_factory()
        try:
            assert session.get_bind() is engine
        finally:
            session.close()
    finally:
        engine.dispose()
