"""Base dos schemas de entrada: rejeita campos extras e o caractere nulo."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class EntradaBase(BaseModel):
    """Corpo de requisição estrito.

    O PostgreSQL não aceita o caractere nulo (U+0000) em texto; sem esta barreira
    ele chegaria ao banco e viraria erro 500. Vale para todo campo textual,
    inclusive os que forem criados depois.
    """

    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="after")
    @classmethod
    def _recusar_caractere_nulo(cls, valor: Any) -> Any:
        if isinstance(valor, str) and "\x00" in valor:
            raise ValueError("O texto não pode conter o caractere nulo.")
        return valor
