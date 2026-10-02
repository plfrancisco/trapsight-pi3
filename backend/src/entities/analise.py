"""Entidade que registra o resultado de uma análise de imagem."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.entities.base import Base, UUIDTimestampMixin

if TYPE_CHECKING:
    from src.entities.refil import Refil


class Analise(UUIDTimestampMixin, Base):
    """Resultado persistido de uma inferência sobre um refil."""

    __tablename__ = "analise"
    __table_args__ = (
        CheckConstraint(
            "percentual_coberto BETWEEN 0 AND 100",
            name="ck_analise_percentual_coberto",
        ),
        CheckConstraint(
            "status IN ('ok', 'atencao', 'trocar')",
            name="ck_analise_status",
        ),
        Index(
            "ix_analise_refil_id_analisado_em",
            "refil_id",
            "analisado_em",
        ),
    )

    refil_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "refil.id",
            name="fk_analise_refil_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    analisado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    percentual_coberto: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    caminho_imagem: Mapped[str] = mapped_column(String, nullable=False)
    modelo_versao: Mapped[str] = mapped_column(String, nullable=False)

    refil: Mapped[Refil] = relationship(
        back_populates="analises",
        cascade="save-update, merge",
    )
