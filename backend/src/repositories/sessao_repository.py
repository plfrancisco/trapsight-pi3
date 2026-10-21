"""Operações de persistência para sessões autenticadas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from src.entities import Sessao


class SessaoRepository:
    """Acessa sessões usando a transação da sessão fornecida."""

    def __init__(self, session: Session) -> None:
        """Guarda a sessão cuja transação será controlada pelo chamador.

        Args:
            session: sessão SQLAlchemy usada em todas as operações deste repositório.
        """
        self._session = session

    def create(
        self,
        *,
        usuario_id: UUID,
        token_hash: str,
        csrf_token: str,
        expira_em: datetime,
        agora: datetime,
        ip: str | None,
        user_agent: str | None,
    ) -> Sessao:
        """Adiciona uma sessão e envia a alteração ao banco.

        Args:
            usuario_id: dono da sessão.
            token_hash: SHA-256 hexadecimal do token entregue ao navegador.
            csrf_token: token CSRF sincronizado com a sessão.
            expira_em: fim absoluto da sessão.
            agora: instante de criação e do primeiro uso.
            ip: endereço de origem, para auditoria.
            user_agent: agente do navegador, para auditoria.

        Returns:
            A sessão persistida dentro da transação atual.
        """
        sessao = Sessao(
            usuario_id=usuario_id,
            token_hash=token_hash,
            csrf_token=csrf_token,
            expira_em=expira_em,
            ultimo_uso_em=agora,
            ip=ip,
            user_agent=user_agent,
        )
        self._session.add(sessao)
        self._session.flush()
        return sessao

    def get_by_id(self, sessao_id: UUID) -> Sessao | None:
        """Busca a sessão pela chave primária.

        Args:
            sessao_id: UUID da sessão.

        Returns:
            A sessão encontrada ou None.
        """
        return self._session.get(Sessao, sessao_id)

    def get_by_token_hash(self, token_hash: str) -> Sessao | None:
        """Busca a sessão pelo hash do token.

        Args:
            token_hash: SHA-256 hexadecimal do token apresentado.

        Returns:
            A sessão encontrada (válida ou não) ou None.
        """
        statement = select(Sessao).where(Sessao.token_hash == token_hash)
        return self._session.scalars(statement).one_or_none()

    def tocar_uso(self, sessao: Sessao, *, agora: datetime) -> None:
        """Atualiza o instante do último uso.

        Args:
            sessao: sessão utilizada.
            agora: instante do uso.
        """
        sessao.ultimo_uso_em = agora
        self._session.flush()

    def revogar(self, sessao: Sessao, *, agora: datetime) -> None:
        """Marca a sessão como revogada no servidor.

        Args:
            sessao: sessão a revogar.
            agora: instante da revogação.
        """
        if sessao.revogada_em is None:
            sessao.revogada_em = agora
            self._session.flush()

    def revogar_todas(
        self,
        usuario_id: UUID,
        *,
        agora: datetime,
        exceto: UUID | None = None,
    ) -> int:
        """Revoga todas as sessões ainda abertas de um usuário.

        Args:
            usuario_id: dono das sessões.
            agora: instante da revogação.
            exceto: sessão que deve permanecer, quando houver.

        Returns:
            Quantidade de sessões revogadas.
        """
        statement = (
            update(Sessao)
            .where(Sessao.usuario_id == usuario_id, Sessao.revogada_em.is_(None))
            .values(revogada_em=agora)
        )
        if exceto is not None:
            statement = statement.where(Sessao.id != exceto)
        resultado = self._session.execute(statement.execution_options(synchronize_session="fetch"))
        return resultado.rowcount

    def list_abertas(self, usuario_id: UUID) -> list[Sessao]:
        """Lista as sessões não revogadas de um usuário, da menos à mais recentemente usada.

        Args:
            usuario_id: dono das sessões.

        Returns:
            Sessões sem revogação; o chamador ainda confere expiração e inatividade.
        """
        statement = (
            select(Sessao)
            .where(Sessao.usuario_id == usuario_id, Sessao.revogada_em.is_(None))
            .order_by(Sessao.ultimo_uso_em, Sessao.criado_em, Sessao.id)
        )
        return list(self._session.scalars(statement))

    def apagar_expiradas(self, *, agora: datetime) -> int:
        """Remove sessões cujo prazo absoluto já passou.

        Args:
            agora: instante de referência.

        Returns:
            Quantidade de sessões removidas.
        """
        resultado = self._session.execute(delete(Sessao).where(Sessao.expira_em < agora))
        return resultado.rowcount
