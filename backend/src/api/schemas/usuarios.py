"""Contratos estritos de criação e projeção pública de contas."""

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.api.schemas.entrada import EntradaBase
from src.entities.papel import PapelUsuario
from src.services.autenticacao import normalizar_email


class UsuarioEntrada(EntradaBase):
    """Conta de operador; papel e estado não podem ser definidos pelo cliente."""

    email: str = Field(min_length=3, max_length=254)
    nome: str = Field(min_length=1, max_length=120)
    senha: str = Field(min_length=1, max_length=1024, repr=False)

    @field_validator("email", mode="before")
    @classmethod
    def normalizar_endereco(cls, valor: str) -> str:
        """Normaliza o endereço antes de validar limites e unicidade."""
        if not isinstance(valor, str):
            raise ValueError("Informe um e-mail.")
        valor = normalizar_email(valor)
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", valor):
            raise ValueError("Informe um e-mail válido.")
        return valor

    @field_validator("nome", mode="before")
    @classmethod
    def aparar_nome(cls, valor: str) -> str:
        """Desconsidera espaços nas pontas sem aceitar um nome vazio."""
        if not isinstance(valor, str):
            raise ValueError("Informe um nome.")
        return valor.strip()


class ContaSaida(BaseModel):
    """Projeção explícita de conta, sem campos de senha ou sessão."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    nome: str
    papel: PapelUsuario
    ativo: bool
    ultimo_login_em: datetime | None
    criado_em: datetime
