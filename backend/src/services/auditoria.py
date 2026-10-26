"""Registro de eventos de autenticação para auditoria, sem dados sensíveis."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from logging import INFO, Formatter, StreamHandler, getLogger
from typing import Final
from uuid import UUID

logger = getLogger("trapsight.auditoria")
_NOME_HANDLER = "trapsight.auditoria.stdout"

# Só estes campos podem aparecer: nunca senha, hash, token, CSRF nem e-mail digitado.
_CAMPOS_PERMITIDOS: Final = frozenset(
    {"usuario_id", "sessao_id", "ip", "motivo", "criado_por_id"}
)


class _FormatadorAuditoria(Formatter):
    """Formata cada registro com instante UTC e a mensagem estruturada."""

    def format(self, record) -> str:
        """Devolve o registro com timestamp ISO 8601 em UTC."""
        instante = datetime.fromtimestamp(record.created, timezone.utc).isoformat(
            timespec="milliseconds"
        )
        return f"{instante} {record.getMessage()}"


def configurar_auditoria() -> None:
    """Envia eventos de auditoria ao stdout sem repetir os logs do servidor.

    A configuração é idempotente porque a fábrica da aplicação também é usada
    pelos testes e por processos que instanciam mais de uma aplicação.
    """
    logger.setLevel(INFO)
    logger.propagate = False
    for handler_existente in tuple(logger.handlers):
        if handler_existente.get_name() == _NOME_HANDLER:
            logger.removeHandler(handler_existente)
    handler = StreamHandler(sys.stdout)
    handler.set_name(_NOME_HANDLER)
    handler.setFormatter(_FormatadorAuditoria())
    logger.addHandler(handler)


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
