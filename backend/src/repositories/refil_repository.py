"""Operações de persistência para ciclos de refil."""

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.entities import Refil
from src.repositories.exceptions import RefilAtivoExistente


class RefilRepository:
    """Acessa refis sem assumir o controle da transação."""

    def __init__(self, session: Session) -> None:
        """Guarda a sessão que controla as alterações feitas pelo repositório.

        Args:
            session: sessão SQLAlchemy usada em todas as operações deste repositório.
        """
        self._session = session

    def create(
        self,
        *,
        armadilha_id: UUID,
        data_instalacao: date,
        data_troca: date | None = None,
    ) -> Refil:
        """Cria um ciclo de refil associado a uma armadilha.

        Args:
            armadilha_id: UUID da armadilha proprietária.
            data_instalacao: início do ciclo.
            data_troca: data de encerramento, se o ciclo já terminou.

        Returns:
            O refil persistido dentro da transação atual.

        Raises:
            RefilAtivoExistente: se a armadilha já tiver um ciclo aberto.
        """
        refil = Refil(
            armadilha_id=armadilha_id,
            data_instalacao=data_instalacao,
            data_troca=data_troca,
        )
        self._session.add(refil)
        if data_troca is None:
            self._flush_or_raise_active_duplicate()
        else:
            self._session.flush()
        return refil

    def _flush_or_raise_active_duplicate(self) -> None:
        """Converte apenas a violação do índice de refil ativo em erro de domínio."""
        try:
            self._session.flush()
        except IntegrityError as error:
            diagnostic = getattr(error.orig, "diag", None)
            if getattr(diagnostic, "constraint_name", None) == (
                "uq_refil_ativo_por_armadilha"
            ):
                raise RefilAtivoExistente(
                    "Esta armadilha já possui um refil ativo."
                ) from None
            raise

    def get_by_id(self, refil_id: UUID) -> Refil | None:
        """Busca um refil pela chave primária.

        Args:
            refil_id: UUID do refil.

        Returns:
            O refil encontrado ou None.
        """
        return self._session.get(Refil, refil_id)

    def get_active_for_armadilha(self, armadilha_id: UUID) -> Refil | None:
        """Busca o único refil sem data de troca da armadilha.

        Args:
            armadilha_id: UUID da armadilha proprietária.

        Returns:
            O refil ativo ou None; múltiplos resultados revelam dados ambíguos.
        """
        statement = select(Refil).where(
            Refil.armadilha_id == armadilha_id,
            Refil.data_troca.is_(None),
        )
        return self._session.scalars(statement).one_or_none()

    def list_closed_for_armadilha(self, armadilha_id: UUID) -> list[Refil]:
        """Lista ciclos encerrados pela data de troca e UUID.

        Args:
            armadilha_id: UUID da armadilha proprietária.

        Returns:
            Refis encerrados em ordem cronológica.
        """
        statement = (
            select(Refil)
            .where(
                Refil.armadilha_id == armadilha_id,
                Refil.data_troca.is_not(None),
            )
            .order_by(Refil.data_troca.asc(), Refil.id.asc())
        )
        return list(self._session.scalars(statement))

    def close(self, refil_id: UUID, data_troca: date) -> Refil | None:
        """Encerra o ciclo na data informada, deixando a CHECK validar a cronologia.

        Args:
            refil_id: UUID do refil a encerrar.
            data_troca: data em que o refil saiu de uso.

        Returns:
            O refil encerrado ou None se não existir.
        """
        refil = self.get_by_id(refil_id)
        if refil is None:
            return None
        refil.data_troca = data_troca
        self._session.flush()
        return refil
