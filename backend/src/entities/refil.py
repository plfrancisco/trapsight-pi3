"""Entidade que representa o ciclo de uso de um refil adesivo."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.entities.base import Base, UUIDTimestampMixin

if TYPE_CHECKING:
    from src.entities.analise import Analise
    from src.entities.armadilha import Armadilha


class Refil(UUIDTimestampMixin, Base):
    """Refil vinculado a uma armadilha e encerrado na data de troca."""

    __tablename__ = "refil"
    __table_args__ = (
        CheckConstraint(
            "data_troca IS NULL OR data_troca >= data_instalacao",
            name="ck_refil_datas",
        ),
        Index("ix_refil_armadilha_id", "armadilha_id"),
    )

    armadilha_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "armadilha.id",
            name="fk_refil_armadilha_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    data_instalacao: Mapped[date] = mapped_column(Date, nullable=False)
    data_troca: Mapped[date | None] = mapped_column(Date, nullable=True)

    armadilha: Mapped[Armadilha] = relationship(
        back_populates="refis",
        cascade="save-update, merge",
    )
    analises: Mapped[list[Analise]] = relationship(
        back_populates="refil",
        cascade="save-update, merge",
        passive_deletes="all",
    )
