"""Schemas HTTP para cadastro, atualização e consulta de armadilhas."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from src.api.schemas.entrada import EntradaBase
from src.entities import StatusAnalise


def _validar_identificador(valor: str) -> str:
    """Preserva o código recebido e rejeita espaços nas extremidades."""
    if valor != valor.strip():
        raise ValueError("O identificador não pode ter espaços nas pontas.")
    return valor


class ArmadilhaCriar(EntradaBase):
    """Valida os campos aceitos no cadastro de uma armadilha."""

    identificador: str = Field(min_length=1, max_length=64)
    modelo_id: UUID | None = None
    localizacao: str | None = Field(default=None, max_length=200)
    data_instalacao: date | None = None
    criar_refil_inicial: bool = False

    @field_validator("identificador")
    @classmethod
    def _validar_identificador_sem_espacos_nas_pontas(cls, valor: str) -> str:
        """Rejeita espaços externos para manter a chave legível e previsível."""
        return _validar_identificador(valor)

    @model_validator(mode="after")
    def _validar_data_do_refil_inicial(self) -> ArmadilhaCriar:
        """Exige data quando o cadastro também inicia um ciclo de refil."""
        if self.criar_refil_inicial and self.data_instalacao is None:
            raise ValueError("A data de instalação é obrigatória para o refil inicial.")
        return self

    @property
    def data_instalacao_refil_inicial(self) -> date:
        """Retorna a data tipada que o ciclo inicial exige após a validação."""
        if not self.criar_refil_inicial or self.data_instalacao is None:
            raise ValueError("A data de instalação é obrigatória para o refil inicial.")
        return self.data_instalacao


class ArmadilhaAtualizar(EntradaBase):
    """Valida uma atualização parcial sem permitir mudar datas históricas."""

    identificador: str | None = Field(default=None, min_length=1, max_length=64)
    modelo_id: UUID | None = None
    localizacao: str | None = Field(default=None, max_length=200)

    @field_validator("identificador")
    @classmethod
    def _validar_identificador_sem_espacos_nas_pontas(
        cls,
        valor: str | None,
    ) -> str | None:
        """Rejeita espaços externos sem alterar o identificador informado."""
        return None if valor is None else _validar_identificador(valor)

    @model_validator(mode="after")
    def _validar_campos_enviados(self) -> ArmadilhaAtualizar:
        """Exige ao menos um campo editável na atualização parcial."""
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualizar.")
        if "identificador" in self.model_fields_set and self.identificador is None:
            raise ValueError("O identificador não pode ser nulo.")
        return self


class RefilAtivoSaida(BaseModel):
    """Resumo do ciclo atualmente instalado."""

    id: UUID
    data_instalacao: date
    dias_em_uso: int


class RefilAnteriorSaida(BaseModel):
    """Resumo de um ciclo já encerrado."""

    id: UUID
    data_instalacao: date
    data_troca: date
    dias_ate_troca: int


class ArmadilhaLista(BaseModel):
    """Representa o estado consolidado de uma armadilha na listagem."""

    id: UUID
    identificador: str
    localizacao: str | None
    modelo: str | None
    modelo_id: UUID | None
    refil_ativo: RefilAtivoSaida | None
    percentual_atual: Decimal | None
    status: StatusAnalise | None
    dias_ate_saturar: int | None
    limiar_trocar: Decimal
    foto_tipo: Literal["padrao", "real"]
    foto_url: str | None
    ultima_analise_em: datetime | None
    em_alerta_desde: datetime | None

    @field_serializer("percentual_atual", "limiar_trocar", when_used="json")
    def _serializar_percentual(self, valor: Decimal | None) -> float | None:
        """Emite percentuais e o limiar como números JSON em vez de strings decimais."""
        return None if valor is None else float(valor)

    @field_serializer("ultima_analise_em", "em_alerta_desde", when_used="json")
    def _serializar_instante_utc(self, valor: datetime | None) -> str | None:
        """Normaliza instantes ao sufixo UTC usado pelos clientes da API."""
        if valor is None:
            return None
        if valor.tzinfo is None or valor.utcoffset() is None:
            raise ValueError("O instante da análise deve incluir fuso horário.")
        return valor.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class ArmadilhaDetalhe(BaseModel):
    """Representa a armadilha com o refil atual e os ciclos anteriores."""

    id: UUID
    identificador: str
    modelo: str | None
    modelo_id: UUID | None
    localizacao: str | None
    data_instalacao: date | None
    removida_em: datetime | None = None
    refil_ativo: RefilAtivoSaida | None
    refis_anteriores: list[RefilAnteriorSaida]
    percentual_atual: Decimal | None
    status: StatusAnalise | None
    dias_ate_saturar: int | None
    limiar_trocar: Decimal
    foto_tipo: Literal["padrao", "real"]
    foto_url: str | None

    @field_serializer("percentual_atual", "limiar_trocar", when_used="json")
    def _serializar_percentual(self, valor: Decimal | None) -> float | None:
        """Emite percentuais e o limiar como números JSON em vez de strings decimais."""
        return None if valor is None else float(valor)
