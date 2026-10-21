"""Operações de persistência para tentativas de login."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from src.entities import TentativaLogin


class TentativaLoginRepository:
    """Registra e conta tentativas usando a transação da sessão fornecida."""

    def __init__(self, session: Session) -> None:
        """Guarda a sessão cuja transação será controlada pelo chamador.

        Args:
            session: sessão SQLAlchemy usada em todas as operações deste repositório.
        """
        self._session = session

    def registrar(
        self,
        *,
        identificador_hash: str,
        ip: str,
        sucesso: bool,
        agora: datetime,
    ) -> None:
        """Grava uma tentativa de login.

        Args:
            identificador_hash: hash do e-mail normalizado.
            ip: endereço de origem.
            sucesso: se a autenticação foi concluída.
            agora: instante da tentativa.
        """
        self._session.add(
            TentativaLogin(
                identificador_hash=identificador_hash,
                ip=ip,
                sucesso=sucesso,
                ocorrida_em=agora,
            )
        )
        self._session.flush()

    def contar_falhas_por_ip(self, ip: str, *, desde: datetime) -> int:
        """Conta as falhas de um endereço na janela.

        Args:
            ip: endereço de origem.
            desde: início da janela.

        Returns:
            Quantidade de falhas desde o início da janela.
        """
        statement = select(func.count()).where(
            TentativaLogin.ip == ip,
            TentativaLogin.sucesso.is_(False),
            TentativaLogin.ocorrida_em >= desde,
        )
        return int(self._session.scalar(statement) or 0)

    def contar_falhas_por_conta(
        self, identificador_hash: str, *, desde: datetime
    ) -> int:
        """Conta as falhas de uma conta na janela, a partir do último sucesso.

        Um login bem-sucedido zera o contador da conta.

        Args:
            identificador_hash: hash do e-mail normalizado.
            desde: início da janela.

        Returns:
            Quantidade de falhas consecutivas dentro da janela.
        """
        ultimo_sucesso = (
            select(func.max(TentativaLogin.ocorrida_em))
            .where(
                TentativaLogin.identificador_hash == identificador_hash,
                TentativaLogin.sucesso.is_(True),
            )
            .scalar_subquery()
        )
        statement = select(func.count()).where(
            TentativaLogin.identificador_hash == identificador_hash,
            TentativaLogin.sucesso.is_(False),
            TentativaLogin.ocorrida_em >= desde,
            or_(ultimo_sucesso.is_(None), TentativaLogin.ocorrida_em > ultimo_sucesso),
        )
        return int(self._session.scalar(statement) or 0)

    def apagar_falhas_da_conta(self, identificador_hash: str) -> int:
        """Descarta as falhas de uma conta (desbloqueio feito pelo administrador).

        Args:
            identificador_hash: hash do e-mail normalizado.

        Returns:
            Quantidade de registros removidos.
        """
        resultado = self._session.execute(
            delete(TentativaLogin).where(
                TentativaLogin.identificador_hash == identificador_hash,
                TentativaLogin.sucesso.is_(False),
            )
        )
        return resultado.rowcount

    def apagar_anteriores_a(self, limite: datetime) -> int:
        """Remove registros antigos, que não influenciam mais nenhuma janela.

        Args:
            limite: registros anteriores a este instante são removidos.

        Returns:
            Quantidade de registros removidos.
        """
        resultado = self._session.execute(
            delete(TentativaLogin).where(TentativaLogin.ocorrida_em < limite)
        )
        return resultado.rowcount
