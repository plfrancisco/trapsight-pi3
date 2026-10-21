"""Entidade que representa um modelo de armadilha do catálogo do fabricante."""

from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from src.entities.base import Base, UUIDTimestampMixin


class ModeloArmadilha(UUIDTimestampMixin, Base):
    """Modelo fabricado e pré-cadastrado, escolhido ao registrar uma armadilha."""

    __tablename__ = "modelo_armadilha"
    __table_args__ = (
        UniqueConstraint("codigo", name="uq_modelo_armadilha_codigo"),
        CheckConstraint(
            "refil_largura_mm > 0 AND refil_altura_mm > 0",
            name="ck_modelo_armadilha_refil_positivo",
        ),
    )

    codigo: Mapped[str] = mapped_column(String, nullable=False)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    fabricante: Mapped[str] = mapped_column(String, nullable=False)
    descricao: Mapped[str | None] = mapped_column(String, nullable=True)
    atracao: Mapped[str | None] = mapped_column(String, nullable=True)
    refil_largura_mm: Mapped[int] = mapped_column(Integer, nullable=False)
    refil_altura_mm: Mapped[int] = mapped_column(Integer, nullable=False)
    ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
