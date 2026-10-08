"""Schemas HTTP para registrar e apresentar a troca de um refil."""

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RefilTrocaCriar(BaseModel):
    """Valida a data de início do novo ciclo de refil."""

    model_config = ConfigDict(extra="forbid")

    data_instalacao: date


class RefilEncerradoSaida(BaseModel):
    """Representa o ciclo finalizado pela troca."""

    id: UUID
    data_instalacao: date
    data_troca: date
    dias_ate_troca: int


class RefilNovoSaida(BaseModel):
    """Representa o ciclo criado pela troca."""

    id: UUID
    data_instalacao: date
    dias_em_uso: int


class RefilTrocaSaida(BaseModel):
    """Apresenta o ciclo encerrado, quando existe, e o novo ciclo ativo."""

    refil_encerrado: RefilEncerradoSaida | None
    refil_novo: RefilNovoSaida
