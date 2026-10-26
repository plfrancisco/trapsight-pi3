"""Registro de eventos de autenticação para auditoria, sem dados sensíveis."""

from __future__ import annotations

from logging import getLogger
from typing import Final
from uuid import UUID

logger = getLogger("trapsight.auditoria")

# Só estes campos podem aparecer: nunca senha, hash, token, CSRF nem e-mail digitado.
_CAMPOS_PERMITIDOS: Final = frozenset(
    {"usuario_id", "sessao_id", "ip", "motivo", "criado_por_id"}
)


def registrar_evento(evento: str, **campos: str | UUID | None) -> None:
    """Escreve um evento de autenticação em uma linha `chave=valor`.

    Args:
        evento: nome estável do evento (ex.: `login_falhou`, `login_bloqueado`).
        **campos: contexto com IDs de usuário, sessão e criador, IP e motivo.

    Raises:
        ValueError: se algum campo fora da lista permitida for informado.
    """
    desconhecidos = set(campos) - _CAMPOS_PERMITIDOS
    if desconhecidos:
        raise ValueError(f"Campos não permitidos na auditoria: {sorted(desconhecidos)}")

    contexto = " ".join(
        f"{nome}={valor}" for nome, valor in sorted(campos.items()) if valor is not None
    )
    logger.info("auth.%s %s", evento, contexto)
