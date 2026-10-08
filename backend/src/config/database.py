"""Criação de engine e fábrica de sessões para PostgreSQL."""

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import Session, sessionmaker


class DatabaseConfigurationError(ValueError):
    """Indica configuração ausente ou inválida sem revelar dados de conexão."""


def database_url_from_environment() -> URL:
    """Valida DATABASE_URL e devolve uma URL configurada para Psycopg 3.

    Returns:
        URL SQLAlchemy pronta para criar um engine PostgreSQL.

    Raises:
        DatabaseConfigurationError: se a URL estiver ausente ou inválida.
    """
    value = os.environ.get("DATABASE_URL")
    if not value:
        raise DatabaseConfigurationError(
            "DATABASE_URL não definida; configure a variável de ambiente."
        )

    return _validated_database_url(value)


def _validated_database_url(value: str | URL) -> URL:
    """Valida uma URL sem reproduzir seu conteúdo em mensagens de erro."""

    try:
        url = value if isinstance(value, URL) else make_url(value)
        _validate_url_port(url)
    except (ArgumentError, ValueError):
        raise DatabaseConfigurationError(
            "DATABASE_URL inválida; verifique sua configuração."
        ) from None

    if url.drivername not in {"postgresql", "postgresql+psycopg"}:
        raise DatabaseConfigurationError(
            "DATABASE_URL deve usar PostgreSQL com Psycopg 3."
        )

    return url.set(drivername="postgresql+psycopg")


def _validate_url_port(url: URL) -> None:
    """Converte a porta textual para detectar valores inválidos na inicialização."""
    _ = url.port


def create_database_engine(database_url: str | URL | None = None) -> Engine:
    """Cria um engine Psycopg com parâmetros ocultos em logs.

    Args:
        database_url: URL validada pelo chamador ou None para ler o ambiente.

    Returns:
        Engine configurado para PostgreSQL com verificação de conexão.

    Raises:
        DatabaseConfigurationError: se DATABASE_URL estiver ausente ou inválida.
    """
    url = (
        database_url_from_environment()
        if database_url is None
        else _validated_database_url(database_url)
    )
    return create_engine(
        url,
        pool_pre_ping=True,
        hide_parameters=True,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Cria uma fábrica de sessões ligada ao engine recebido.

    Args:
        engine: engine cujo ciclo de vida é controlado pelo chamador.

    Returns:
        Fábrica de sessões sem assumir o controle de commit da aplicação.
    """
    return sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=True,
        expire_on_commit=False,
    )
