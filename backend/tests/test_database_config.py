"""Verifica a leitura segura da configuração de conexão."""

import pytest

from src.config.database import (
    DatabaseConfigurationError,
    create_database_engine,
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
