"""Persistência dos eventos administrativos da CLI."""

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from src.entities.auditoria_cli import AuditoriaCLI


class AuditoriaCLIRepository:
    """Insere eventos dentro da transação controlada pelo comando."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def registrar(
        self,
        *,
        ocorrido_em: datetime,
        evento: str,
        executor: str,
        conta_alvo: UUID | None,
        resultado: str,
        detalhe: str,
    ) -> AuditoriaCLI:
        """Adiciona um evento sem confirmar a transação do chamador."""
        registro = AuditoriaCLI(
            ocorrido_em=ocorrido_em,
            evento=evento,
            executor=executor[:255],
            conta_alvo=conta_alvo,
            resultado=resultado,
            detalhe=detalhe[:240],
        )
        self._session.add(registro)
        self._session.flush()
        return registro
