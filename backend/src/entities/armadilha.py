"""Entidade que representa uma armadilha instalada."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.entities.base import Base, UUIDTimestampMixin

if TYPE_CHECKING:
    from src.entities.refil import Refil


class Armadilha(UUIDTimestampMixin, Base):
    """Armadilha identificada pelo código único usado em campo."""

    __tablename__ = "armadilha"
    __table_args__ = (
        UniqueConstraint("identificador", name="uq_armadilha_identificador"),
    )

    identificador: Mapped[str] = mapped_column(String, nullable=False)
    modelo: Mapped[str | None] = mapped_column(String, nullable=True)
    modelo_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("modelo_armadilha.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    localizacao: Mapped[str | None] = mapped_column(String, nullable=True)
    data_instalacao: Mapped[date | None] = mapped_column(nullable=True)
    removida_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Cópia reduzida (JPEG, sem EXIF) da foto real; nula usa a foto padrão do
    # modelo. Adiada para que listar armadilhas nunca leia o blob.
    foto_identificacao: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True, deferred=True
    )
    foto_atualizada_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    refis: Mapped[list[Refil]] = relationship(
        back_populates="armadilha",
        cascade="save-update, merge",
        passive_deletes="all",
    )
