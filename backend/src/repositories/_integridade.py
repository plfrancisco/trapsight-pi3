"""Utilitários para interpretar violações de integridade do banco."""

from sqlalchemy.exc import IntegrityError


def nome_constraint_violada(error: IntegrityError) -> str | None:
    """Retorna o nome da constraint reportado pelo driver PostgreSQL.

    Args:
        error: erro de integridade produzido pelo SQLAlchemy.

    Returns:
        Nome da constraint violada, ou None quando o driver não o informa.
    """
    diagnostic = getattr(error.orig, "diag", None)
    name = getattr(diagnostic, "constraint_name", None)
    return name if isinstance(name, str) else None
