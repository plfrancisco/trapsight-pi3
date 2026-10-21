"""Schema HTTP do catálogo de modelos de armadilha."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ModeloArmadilhaSaida(BaseModel):
    """Modelo do fabricante exibido no cadastro de armadilhas."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    codigo: str
    nome: str
    fabricante: str
    descricao: str | None
    atracao: str | None
    refil_largura_mm: int
    refil_altura_mm: int
