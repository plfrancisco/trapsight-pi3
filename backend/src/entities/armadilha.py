"""Entidade que representa uma armadilha instalada."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import String, UniqueConstraint
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
    localizacao: Mapped[str | None] = mapped_column(String, nullable=True)
    data_instalacao: Mapped[date | None] = mapped_column(nullable=True)

    refis: Mapped[list[Refil]] = relationship(
        back_populates="armadilha",
        cascade="save-update, merge",
        passive_deletes="all",
    )
