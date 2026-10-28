"""Evento durável de uma ação administrativa executada pela CLI."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from src.entities.base import Base


class AuditoriaCLI(Base):
    """Registro append-only de uma ação administrativa e seu resultado."""

    __tablename__ = "auditoria_cli"
    __table_args__ = (
        CheckConstraint(
            "evento IN ('criar-usuario', 'definir-papel', 'redefinir-senha', "
            "'ativar-usuario', 'desativar-usuario', 'desbloquear-usuario')",
            name="ck_auditoria_cli_evento",
        ),
        CheckConstraint(
            "resultado IN ('sucesso', 'falha')", name="ck_auditoria_cli_resultado"
        ),
        Index("ix_auditoria_cli_ocorrido_em", "ocorrido_em"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    ocorrido_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    evento: Mapped[str] = mapped_column(String(32), nullable=False)
    executor: Mapped[str] = mapped_column(String(255), nullable=False)
    # UUID evita armazenar e-mails digitados, que podem conter credenciais por engano.
    conta_alvo: Mapped[UUID | None] = mapped_column(nullable=True)
    resultado: Mapped[str] = mapped_column(String(8), nullable=False)
    detalhe: Mapped[str] = mapped_column(String(240), nullable=False)
