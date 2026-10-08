"""Operações de persistência e leitura temporal para análises."""

from collections.abc import Collection
from datetime import datetime
from decimal import Decimal
from typing import NamedTuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from src.entities import Analise, Refil, StatusAnalise


class PontoAnalise(NamedTuple):
    """Projeção enxuta de uma leitura persistida para gráficos e resumos."""

    analisado_em: datetime
    percentual_coberto: Decimal
    status: StatusAnalise


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
        status: StatusAnalise,
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
            status=StatusAnalise(status).value,
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

    def list_by_refil(
        self,
        refil_id: UUID,
        *,
        limit: int | None = 100,
    ) -> list[Analise]:
        """Lista as análises mais recentes do refil em ordem cronológica.

        Args:
            refil_id: UUID do ciclo analisado.
            limit: quantidade máxima de registros; None retorna todos.

        Returns:
            As análises selecionadas da mais antiga para a mais recente.

        Raises:
            ValueError: se limit for menor que um quando informado.
        """
        statement = select(Analise).where(Analise.refil_id == refil_id)
        return self._list_latest(statement, limit)

    def list_by_armadilha(
        self,
        armadilha_id: UUID,
        *,
        limit: int | None = 100,
    ) -> list[Analise]:
        """Lista as análises mais recentes da armadilha em ordem cronológica.

        Args:
            armadilha_id: UUID da armadilha proprietária dos refis.
            limit: quantidade máxima de registros; None retorna todos.

        Returns:
            As análises selecionadas da mais antiga para a mais recente.

        Raises:
            ValueError: se limit for menor que um quando informado.
        """
        statement = (
            select(Analise)
            .join(Refil, Analise.refil_id == Refil.id)
            .where(Refil.armadilha_id == armadilha_id)
        )
        return self._list_latest(statement, limit)

    def _list_latest(
        self,
        filtered_statement: Select[tuple[Analise]],
        limit: int | None,
    ) -> list[Analise]:
        """Limita pela recência e devolve os registros em ordem cronológica."""
        self._validate_limit(limit)
        if limit is not None:
            latest_ids = (
                filtered_statement.with_only_columns(Analise.id)
                .order_by(Analise.analisado_em.desc(), Analise.id.desc())
                .limit(limit)
                .subquery()
            )
            filtered_statement = select(Analise).join(
                latest_ids, Analise.id == latest_ids.c.id
            )

        statement = filtered_statement.order_by(
            Analise.analisado_em.asc(), Analise.id.asc()
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

    def list_pontos_by_refil_ids(
        self,
        refil_ids: Collection[UUID],
    ) -> dict[UUID, list[PontoAnalise]]:
        """Lê pontos de vários refis em um SELECT sem carregar entidades.

        Args:
            refil_ids: identificadores dos ciclos cujas análises serão projetadas.

        Returns:
            Pontos agrupados por refil e ordenados cronologicamente.
        """
        identificadores = set(refil_ids)
        pontos_por_refil = {refil_id: [] for refil_id in identificadores}
        statement = (
            select(
                Analise.refil_id,
                Analise.analisado_em,
                Analise.percentual_coberto,
                Analise.status,
            )
            .where(Analise.refil_id.in_(identificadores))
            .order_by(
                Analise.refil_id.asc(),
                Analise.analisado_em.asc(),
                Analise.id.asc(),
            )
        )
        for row in self._session.execute(statement):
            pontos_por_refil[row.refil_id].append(
                PontoAnalise(
                    analisado_em=row.analisado_em,
                    percentual_coberto=row.percentual_coberto,
                    status=StatusAnalise(row.status),
                )
            )
        return pontos_por_refil

    @staticmethod
    def _validate_limit(limit: int | None) -> None:
        """Rejeita limites que resultariam em leitura vazia inesperada."""
        if limit is not None and limit < 1:
            raise ValueError("limit deve ser maior que zero.")
