"""Operações de persistência para armadilhas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Final
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.entities import Armadilha
from src.repositories._integridade import nome_constraint_violada
from src.repositories.exceptions import IdentificadorDuplicado


class _Unset:
    """Sentinela para distinguir campos omitidos de valores nulos explícitos."""


_UNSET: Final = _Unset()


class ArmadilhaRepository:
    """Acessa armadilhas usando a transação da sessão fornecida."""

    def __init__(self, session: Session) -> None:
        """Guarda a sessão cuja transação será controlada pelo chamador.

        Args:
            session: sessão SQLAlchemy usada em todas as operações deste repositório.
        """
        self._session = session

    def create(
        self,
        *,
        identificador: str,
        modelo: str | None = None,
        modelo_id: UUID | None = None,
        localizacao: str | None = None,
        data_instalacao: date | None = None,
    ) -> Armadilha:
        """Adiciona uma armadilha e envia alterações ao banco para obter seu UUID.

        Args:
            identificador: código único que identifica a armadilha em campo.
            modelo: nome do modelo físico, quando conhecido.
            modelo_id: modelo do catálogo a que a armadilha pertence, se houver.
            localizacao: ponto de instalação, quando conhecido.
            data_instalacao: data da instalação, quando conhecida.

        Returns:
            A armadilha persistida dentro da transação atual.

        Raises:
            IdentificadorDuplicado: se o código já estiver cadastrado.
        """
        armadilha = Armadilha(
            identificador=identificador,
            modelo=modelo,
            modelo_id=modelo_id,
            localizacao=localizacao,
            data_instalacao=data_instalacao,
        )
        self._session.add(armadilha)
        self._flush_or_raise_duplicate()
        return armadilha

    def get_by_id(self, armadilha_id: UUID) -> Armadilha | None:
        """Busca uma armadilha pela chave primária.

        Args:
            armadilha_id: UUID da armadilha.

        Returns:
            A armadilha encontrada ou None.
        """
        return self._session.get(Armadilha, armadilha_id)

    def get_by_id_ativo(self, armadilha_id: UUID) -> Armadilha | None:
        """Busca uma armadilha disponível para novas operações."""
        statement = select(Armadilha).where(
            Armadilha.id == armadilha_id,
            Armadilha.removida_em.is_(None),
        )
        return self._session.scalars(statement).one_or_none()

    def get_by_id_for_update(self, armadilha_id: UUID) -> Armadilha | None:
        """Busca e bloqueia a linha da armadilha até o fim da transação.

        Args:
            armadilha_id: UUID da armadilha.

        Returns:
            A armadilha bloqueada ou None se não existir.
        """
        statement = (
            select(Armadilha)
            .where(Armadilha.id == armadilha_id, Armadilha.removida_em.is_(None))
            .with_for_update()
        )
        return self._session.scalars(statement).one_or_none()

    def get_by_identificador(self, identificador: str) -> Armadilha | None:
        """Busca uma armadilha pelo código único usado em campo.

        Args:
            identificador: código exato da armadilha.

        Returns:
            A armadilha encontrada ou None.
        """
        statement = select(Armadilha).where(Armadilha.identificador == identificador)
        return self._session.scalars(statement).one_or_none()

    def list_all(self) -> list[Armadilha]:
        """Lista armadilhas em ordem estável pelo identificador.

        Returns:
            Todas as armadilhas visíveis na transação atual.
        """
        statement = (
            select(Armadilha)
            .where(Armadilha.removida_em.is_(None))
            .order_by(Armadilha.identificador)
        )
        return list(self._session.scalars(statement))

    def update(
        self,
        armadilha_id: UUID,
        *,
        identificador: str | _Unset = _UNSET,
        modelo: str | None | _Unset = _UNSET,
        modelo_id: UUID | None | _Unset = _UNSET,
        localizacao: str | None | _Unset = _UNSET,
    ) -> Armadilha | None:
        """Atualiza apenas os campos fornecidos e envia as mudanças ao banco.

        Args:
            armadilha_id: UUID da armadilha a atualizar.
            identificador: novo código, se informado.
            modelo: novo nome do modelo, inclusive None para limpar o campo.
            modelo_id: novo modelo do catálogo, inclusive None para desvincular.
            localizacao: novo local, inclusive None para limpar o campo.

        Returns:
            A armadilha atualizada ou None se não existir.

        Raises:
            IdentificadorDuplicado: se o novo código já estiver cadastrado.
        """
        armadilha = self.get_by_id_ativo(armadilha_id)
        if armadilha is None:
            return None

        changed = False
        if identificador is not _UNSET:
            armadilha.identificador = identificador
            changed = True
        if modelo is not _UNSET:
            armadilha.modelo = modelo
            changed = True
        if modelo_id is not _UNSET:
            armadilha.modelo_id = modelo_id
            changed = True
        if localizacao is not _UNSET:
            armadilha.localizacao = localizacao
            changed = True

        if changed:
            self._flush_or_raise_duplicate()
        return armadilha

    def remover(self, armadilha_id: UUID, removida_em: datetime) -> Armadilha | None:
        """Marca a armadilha como removida sem apagar análises nem refis."""
        armadilha = self.get_by_id_for_update(armadilha_id)
        if armadilha is None:
            return None
        armadilha.removida_em = removida_em
        self._session.flush()
        return armadilha

    def _flush_or_raise_duplicate(self) -> None:
        """Converte apenas a violação do identificador único em erro de domínio."""
        try:
            self._session.flush()
        except IntegrityError as error:
            if nome_constraint_violada(error) == "uq_armadilha_identificador":
                raise IdentificadorDuplicado(
                    "Já existe uma armadilha com este identificador."
                ) from None
            raise
