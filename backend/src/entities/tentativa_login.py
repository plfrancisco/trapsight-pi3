"""Entidade que registra tentativas de login para bloqueio e limite por IP."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from src.entities.base import Base, UUIDTimestampMixin


class TentativaLogin(UUIDTimestampMixin, Base):
    """Tentativa de login; não guarda o e-mail digitado nem a senha."""

    __tablename__ = "tentativa_login"
    __table_args__ = (
        Index(
            "ix_tentativa_login_identificador_hash_ocorrida_em",
            "identificador_hash",
            "ocorrida_em",
        ),
        Index("ix_tentativa_login_ip_ocorrida_em", "ip", "ocorrida_em"),
    )

    # Hash do e-mail normalizado: permite contar por conta sem gravar o texto digitado.
    identificador_hash: Mapped[str] = mapped_column(String, nullable=False)
    ip: Mapped[str] = mapped_column(String, nullable=False)
    ocorrida_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    sucesso: Mapped[bool] = mapped_column(Boolean, nullable=False)
