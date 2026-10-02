"""Fixtures para usar sessões isoladas em um PostgreSQL descartável."""

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from src.config.database import create_database_engine


@pytest.fixture(scope="session")
def engine() -> Engine:
    """Cria o engine usando as credenciais fornecidas pelo ambiente de teste."""
    database_engine = create_database_engine()
    yield database_engine
    database_engine.dispose()


@pytest.fixture
def session(engine: Engine):
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
