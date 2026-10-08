"""Fixtures para usar sessões isoladas em um PostgreSQL descartável."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from src.config.database import create_database_engine


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """Cria o engine usando as credenciais fornecidas pelo ambiente de teste."""
    database_engine = create_database_engine()
    yield database_engine
    database_engine.dispose()


@pytest.fixture(scope="session")
def check_database_revision(engine: Engine) -> None:
    """Exige que o banco esteja na revisão Alembic mais recente antes dos testes."""
    config_path = Path(__file__).resolve().parents[1] / "alembic.ini"
    script_directory = ScriptDirectory.from_config(Config(str(config_path)))
    expected_revision = script_directory.get_current_head()
    with engine.connect() as connection:
        current_revision = MigrationContext.configure(connection).get_current_revision()

    if current_revision != expected_revision:
        pytest.fail(
            "O banco de teste não está na revisão mais recente "
            f"({current_revision!r}; esperada {expected_revision!r}). "
            'Execute "alembic upgrade head" antes de rodar os testes.'
        )


@pytest.fixture
def session(engine: Engine, check_database_revision: None) -> Iterator[Session]:
    """Executa cada teste em savepoint e reverte todas as alterações ao final."""
    connection = engine.connect()
    transaction = connection.begin()
    database_session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    try:
        yield database_session
    finally:
        database_session.close()
        transaction.rollback()
        connection.close()
