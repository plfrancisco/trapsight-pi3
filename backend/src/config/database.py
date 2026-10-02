"""Criação de engine e fábrica de sessões para PostgreSQL."""

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import Session, sessionmaker


class DatabaseConfigurationError(ValueError):
    """Indica configuração ausente ou inválida sem revelar dados de conexão."""


def create_database_engine() -> Engine:
    """Cria um engine Psycopg a partir de DATABASE_URL.

    Returns:
        Engine configurado com verificação de conexão e parâmetros ocultos em logs.

    Raises:
        DatabaseConfigurationError: se DATABASE_URL estiver ausente ou inválida.
    """
    value = os.environ.get("DATABASE_URL")
    if not value:
        raise DatabaseConfigurationError(
            "DATABASE_URL não definida; configure a variável de ambiente."
        )

    try:
        url = make_url(value)
        _ = url.port
    except (ArgumentError, ValueError):
        raise DatabaseConfigurationError(
            "DATABASE_URL inválida; verifique sua configuração."
        ) from None

    if url.drivername not in {"postgresql", "postgresql+psycopg"}:
        raise DatabaseConfigurationError(
            "DATABASE_URL deve usar PostgreSQL com Psycopg 3."
        )

    return create_engine(
        url.set(drivername="postgresql+psycopg"),
        pool_pre_ping=True,
        hide_parameters=True,
    )


def create_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    """Cria uma fábrica de sessões associada ao engine informado ou ao ambiente.

    Args:
        engine: engine existente, útil para compartilhar o ciclo de vida da conexão.

    Returns:
        Fábrica de sessões sem assumir o controle de commit da aplicação.
    """
    return sessionmaker(
        bind=engine if engine is not None else create_database_engine(),
        class_=Session,
        autoflush=True,
        expire_on_commit=False,
    )
