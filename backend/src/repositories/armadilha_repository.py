"""Operações de persistência para armadilhas."""

from __future__ import annotations

from datetime import date
from typing import Final
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.entities import Armadilha
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
        localizacao: str | None = None,
        data_instalacao: date | None = None,
    ) -> Armadilha:
        """Adiciona uma armadilha e envia alterações ao banco para obter seu UUID.

        Args:
            identificador: código único que identifica a armadilha em campo.
            modelo: modelo físico, quando conhecido.
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
        statement = select(Armadilha).order_by(Armadilha.identificador)
        return list(self._session.scalars(statement))

    def update(
        self,
        armadilha_id: UUID,
        *,
        identificador: str | _Unset = _UNSET,
        modelo: str | None | _Unset = _UNSET,
        localizacao: str | None | _Unset = _UNSET,
    ) -> Armadilha | None:
        """Atualiza apenas os campos fornecidos e envia as mudanças ao banco.

        Args:
            armadilha_id: UUID da armadilha a atualizar.
            identificador: novo código, se informado.
            modelo: novo modelo, inclusive None para limpar o campo.
            localizacao: novo local, inclusive None para limpar o campo.

        Returns:
            A armadilha atualizada ou None se não existir.

        Raises:
            IdentificadorDuplicado: se o novo código já estiver cadastrado.
        """
        armadilha = self.get_by_id(armadilha_id)
        if armadilha is None:
            return None

        changed = False
        if identificador is not _UNSET:
            armadilha.identificador = identificador
            changed = True
        if modelo is not _UNSET:
            armadilha.modelo = modelo
            changed = True
        if localizacao is not _UNSET:
            armadilha.localizacao = localizacao
            changed = True

        if changed:
            self._flush_or_raise_duplicate()
        return armadilha

    def _flush_or_raise_duplicate(self) -> None:
        """Converte apenas a violação do identificador único em erro de domínio."""
        try:
            self._session.flush()
        except IntegrityError as error:
            diagnostic = getattr(error.orig, "diag", None)
            if getattr(diagnostic, "constraint_name", None) == (
                "uq_armadilha_identificador"
            ):
                raise IdentificadorDuplicado(
                    "Já existe uma armadilha com este identificador."
                ) from None
            raise
