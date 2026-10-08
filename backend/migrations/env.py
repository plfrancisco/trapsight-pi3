"""Executa as migrations usando somente a conexão definida no ambiente."""

from alembic import context
from alembic.util import CommandError
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import URL

from src.config.database import (
    DatabaseConfigurationError,
    database_url_from_environment,
)
from src.entities import Base

target_metadata = Base.metadata


def database_url() -> URL:
    """Obtém a URL validada e converte falhas em erros próprios do Alembic."""
    try:
        return database_url_from_environment()
    except DatabaseConfigurationError as error:
        raise CommandError(str(error)) from None


def run_migrations_offline() -> None:
    """Gera comandos de migration sem abrir uma conexão com o banco."""
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplica migrations usando uma conexão temporária com o banco."""
    engine = create_engine(
        database_url(),
        # Cada execução usa uma conexão curta; não há benefício em mantê-la no pool.
        poolclass=pool.NullPool,
        # Impede que valores dos parâmetros sejam incluídos em logs de erro SQL.
        hide_parameters=True,
    )
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
