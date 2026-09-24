"""Execute migrations using only the connection configured in the environment."""

import os

from alembic import context
from alembic.util import CommandError
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

target_metadata = None


def database_url():
    """Valida DATABASE_URL e seleciona o driver Psycopg 3 sem expor a URL."""
    value = os.environ.get("DATABASE_URL")
    if not value:
        raise CommandError(
            "DATABASE_URL não definida; configure a variável de ambiente."
        )
    try:
        url = make_url(value)
    except (ArgumentError, ValueError):
        raise CommandError(
            "DATABASE_URL inválida; verifique sua configuração."
        ) from None
    if url.drivername not in {"postgresql", "postgresql+psycopg"}:
        raise CommandError("DATABASE_URL deve usar PostgreSQL com Psycopg 3.")
    return url.set(drivername="postgresql+psycopg")


def run_migrations_offline():
    """Gera comandos de migration sem abrir uma conexão com o banco."""
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
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
