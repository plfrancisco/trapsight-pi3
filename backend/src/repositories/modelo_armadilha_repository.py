"""Consulta ao catálogo de modelos de armadilha."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.entities import ModeloArmadilha


class ModeloArmadilhaRepository:
    """Lê o catálogo usando a transação da sessão fornecida."""

    def __init__(self, session: Session) -> None:
        """Guarda a sessão cuja transação será controlada pelo chamador.

        Args:
            session: sessão SQLAlchemy usada em todas as consultas.
        """
        self._session = session

    def list_ativos(self) -> list[ModeloArmadilha]:
        """Lista os modelos disponíveis para novos cadastros, em ordem estável.

        Returns:
            Modelos ativos ordenados pelo nome.
        """
        statement = (
            select(ModeloArmadilha)
            .where(ModeloArmadilha.ativo.is_(True))
            .order_by(ModeloArmadilha.nome)
        )
        return list(self._session.scalars(statement))

    def get_ativo(self, modelo_id: UUID) -> ModeloArmadilha | None:
        """Busca um modelo que ainda aceita novos cadastros.

        Args:
            modelo_id: UUID do modelo.

        Returns:
            O modelo, ou None se não existir ou estiver desativado.
        """
        modelo = self._session.get(ModeloArmadilha, modelo_id)
        return modelo if modelo is not None and modelo.ativo else None
