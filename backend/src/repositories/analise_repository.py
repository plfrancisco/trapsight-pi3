"""Operações de persistência e leitura temporal para análises."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.entities import Analise, Refil


class AnaliseRepository:
    """Acessa análises sem derivar status nem projeções de negócio."""

    def __init__(self, session: Session) -> None:
        """Guarda a sessão cuja transação será controlada pelo chamador.

        Args:
            session: sessão SQLAlchemy usada em todas as operações deste repositório.
        """
        self._session = session

    def create(
        self,
        *,
        refil_id: UUID,
        analisado_em: datetime,
        percentual_coberto: Decimal,
        status: str,
        caminho_imagem: str,
        modelo_versao: str,
    ) -> Analise:
        """Cria uma análise com o resultado já calculado pela camada de aplicação.

        Args:
            refil_id: UUID do ciclo analisado.
            analisado_em: instante da inferência.
            percentual_coberto: área coberta persistida, entre zero e cem.
            status: classificação persistida no momento da análise.
            caminho_imagem: caminho relativo do arquivo armazenado.
            modelo_versao: versão do modelo que produziu o resultado.

        Returns:
            A análise persistida dentro da transação atual.
        """
        analise = Analise(
            refil_id=refil_id,
            analisado_em=analisado_em,
            percentual_coberto=percentual_coberto,
            status=status,
            caminho_imagem=caminho_imagem,
            modelo_versao=modelo_versao,
        )
        self._session.add(analise)
        self._session.flush()
        return analise

    def get_by_id(self, analise_id: UUID) -> Analise | None:
        """Busca uma análise pela chave primária.

        Args:
            analise_id: UUID da análise.

        Returns:
            A análise encontrada ou None.
        """
        return self._session.get(Analise, analise_id)

    def list_by_refil(self, refil_id: UUID, *, limit: int = 100) -> list[Analise]:
        """Lista análises do refil em ordem cronológica, limitando o resultado.

        Args:
            refil_id: UUID do ciclo analisado.
            limit: quantidade máxima de registros retornados.

        Returns:
            Análises da mais antiga para a mais recente.

        Raises:
            ValueError: se limit for menor que um.
        """
        self._validate_limit(limit)
        statement = (
            select(Analise)
            .where(Analise.refil_id == refil_id)
            .order_by(Analise.analisado_em.asc(), Analise.id.asc())
            .limit(limit)
        )
        return list(self._session.scalars(statement))

    def list_by_armadilha(
        self,
        armadilha_id: UUID,
        *,
        limit: int = 100,
    ) -> list[Analise]:
        """Lista análises de todos os ciclos da armadilha cronologicamente.

        Args:
            armadilha_id: UUID da armadilha proprietária dos refis.
            limit: quantidade máxima de registros retornados.

        Returns:
            Análises da mais antiga para a mais recente.

        Raises:
            ValueError: se limit for menor que um.
        """
        self._validate_limit(limit)
        statement = (
            select(Analise)
            .join(Refil, Analise.refil_id == Refil.id)
            .where(Refil.armadilha_id == armadilha_id)
            .order_by(Analise.analisado_em.asc(), Analise.id.asc())
            .limit(limit)
        )
        return list(self._session.scalars(statement))

    def get_latest_for_refil(self, refil_id: UUID) -> Analise | None:
        """Busca a análise mais recente de um ciclo.

        Args:
            refil_id: UUID do ciclo analisado.

        Returns:
            A análise mais recente ou None.
        """
        statement = (
            select(Analise)
            .where(Analise.refil_id == refil_id)
            .order_by(Analise.analisado_em.desc(), Analise.id.desc())
            .limit(1)
        )
        return self._session.scalars(statement).first()

    @staticmethod
    def _validate_limit(limit: int) -> None:
        """Rejeita limites que resultariam em leitura vazia inesperada."""
        if limit < 1:
            raise ValueError("limit deve ser maior que zero.")
