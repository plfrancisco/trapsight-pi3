"""Entidade que representa uma conta com acesso ao sistema."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.entities.base import Base, UUIDTimestampMixin
from src.entities.papel import PapelUsuario


class Usuario(UUIDTimestampMixin, Base):
    """Conta criada pelo administrador; usuários são desativados, nunca excluídos."""

    __tablename__ = "usuario"
    __table_args__ = (
        UniqueConstraint("email", name="uq_usuario_email"),
        CheckConstraint("papel IN ('gerente', 'operador')", name="ck_usuario_papel"),
        Index(
            "uq_usuario_gerente",
            "papel",
            unique=True,
            postgresql_where=text("papel = 'gerente'"),
        ),
    )

    papel: Mapped[PapelUsuario] = mapped_column(
        Enum(
            PapelUsuario,
            native_enum=False,
            values_callable=lambda papeis: [papel.value for papel in papeis],
        ),
        nullable=False,
        server_default=text("'operador'"),
    )

    email: Mapped[str] = mapped_column(String, nullable=False)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    # String PHC do Argon2id: carrega algoritmo, parâmetros e sal; nunca a senha.
    senha_hash: Mapped[str] = mapped_column(String, nullable=False)
    ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    bloqueado_ate: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    senha_alterada_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    ultimo_login_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
