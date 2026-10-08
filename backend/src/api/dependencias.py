"""Dependências compartilhadas pelas rotas HTTP do backend."""

from collections.abc import Iterator
from datetime import datetime, timezone

from fastapi import Request
from sqlalchemy.orm import Session

from src.config.settings import Settings
from src.inference.contrato import Inferidor


def get_settings(request: Request) -> Settings:
    """Obtém as configurações validadas durante a criação da aplicação.

    Args:
        request: requisição que referencia a aplicação ativa.

    Returns:
        Configuração validada guardada no estado da aplicação.
    """
    return request.app.state.settings


def get_agora() -> datetime:
    """Retorna o instante atual em UTC, substituível por uma dependência de teste.

    Returns:
        Instante atual com fuso horário UTC.
    """
    return datetime.now(timezone.utc)


def get_session(request: Request) -> Iterator[Session]:
    """Abre uma sessão por requisição e reverte o que não tiver sido commitado.

    Args:
        request: requisição que contém a fábrica de sessões da aplicação.

    Yields:
        Sessão SQLAlchemy fechada ao final da requisição.
    """
    session_factory = request.app.state.session_factory
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def get_inferidor(request: Request) -> Inferidor:
    """Obtém a implementação de inferência guardada no estado da aplicação.

    Args:
        request: requisição que referencia a aplicação ativa.

    Returns:
        Implementação de inferência preparada durante a inicialização.
    """
    return request.app.state.inferidor
