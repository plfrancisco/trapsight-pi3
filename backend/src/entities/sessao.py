"""Entidade que representa uma sessão autenticada."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.entities.base import Base, UUIDTimestampMixin


class Sessao(UUIDTimestampMixin, Base):
    """Sessão de um usuário; o token entregue ao navegador nunca é gravado."""

    __tablename__ = "sessao"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_sessao_token_hash"),
        # O banco só aceita o SHA-256 em hexadecimal, nunca um token em claro.
        CheckConstraint(
            "token_hash ~ '^[0-9a-f]{64}$'",
            name="ck_sessao_token_hash_sha256",
        ),
        Index("ix_sessao_usuario_id_revogada_em", "usuario_id", "revogada_em"),
    )

    usuario_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("usuario.id", name="fk_sessao_usuario_id", ondelete="RESTRICT"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    csrf_token: Mapped[str] = mapped_column(String, nullable=False)
    ultimo_uso_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    expira_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revogada_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ip: Mapped[str | None] = mapped_column(String, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String, nullable=True)
