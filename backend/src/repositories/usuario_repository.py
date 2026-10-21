"""Operações de persistência para contas de usuário."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.entities import Usuario
from src.repositories._integridade import nome_constraint_violada
from src.repositories.exceptions import EmailDuplicado


class UsuarioRepository:
    """Acessa usuários usando a transação da sessão fornecida."""

    def __init__(self, session: Session) -> None:
        """Guarda a sessão cuja transação será controlada pelo chamador.

        Args:
            session: sessão SQLAlchemy usada em todas as operações deste repositório.
        """
        self._session = session

    def create(self, *, email: str, nome: str, senha_hash: str) -> Usuario:
        """Adiciona um usuário e envia a alteração ao banco para obter seu UUID.

        Args:
            email: e-mail já normalizado.
            nome: nome de exibição.
            senha_hash: string PHC do Argon2id.

        Returns:
            O usuário persistido dentro da transação atual.

        Raises:
            EmailDuplicado: se o e-mail já estiver cadastrado.
        """
        usuario = Usuario(email=email, nome=nome, senha_hash=senha_hash)
        try:
            # O savepoint preserva a transação do chamador quando a inserção falha.
            with self._session.begin_nested():
                self._session.add(usuario)
                self._session.flush()
        except IntegrityError as error:
            if nome_constraint_violada(error) == "uq_usuario_email":
                raise EmailDuplicado from None
            raise
        return usuario

    def get_by_id(self, usuario_id: UUID) -> Usuario | None:
        """Busca um usuário pela chave primária.

        Args:
            usuario_id: UUID do usuário.

        Returns:
            O usuário encontrado ou None.
        """
        return self._session.get(Usuario, usuario_id)

    def get_by_email(self, email: str) -> Usuario | None:
        """Busca um usuário pelo e-mail normalizado.

        Args:
            email: e-mail exato, já normalizado.

        Returns:
            O usuário encontrado ou None.
        """
        statement = select(Usuario).where(Usuario.email == email)
        return self._session.scalars(statement).one_or_none()

    def list_all(self) -> list[Usuario]:
        """Lista usuários em ordem estável pelo e-mail.

        Returns:
            Todos os usuários visíveis na transação atual.
        """
        statement = select(Usuario).order_by(Usuario.email)
        return list(self._session.scalars(statement))

    def definir_senha_hash(
        self, usuario: Usuario, senha_hash: str, *, agora: datetime
    ) -> None:
        """Grava um novo hash de senha e registra o instante da troca.

        Args:
            usuario: usuário a atualizar.
            senha_hash: nova string PHC.
            agora: instante da troca.
        """
        usuario.senha_hash = senha_hash
        usuario.senha_alterada_em = agora
        self._session.flush()

    def regravar_hash(self, usuario: Usuario, senha_hash: str) -> None:
        """Atualiza o hash com parâmetros novos sem contar como troca de senha.

        Args:
            usuario: usuário autenticado cujo hash ficou desatualizado.
            senha_hash: novo hash da mesma senha.
        """
        usuario.senha_hash = senha_hash
        self._session.flush()

    def definir_ativo(self, usuario: Usuario, *, ativo: bool) -> None:
        """Ativa ou desativa a conta.

        Args:
            usuario: usuário a atualizar.
            ativo: novo estado da conta.
        """
        usuario.ativo = ativo
        self._session.flush()

    def definir_bloqueio(self, usuario: Usuario, bloqueado_ate: datetime | None) -> None:
        """Define ou limpa o bloqueio temporário por tentativas.

        Args:
            usuario: usuário a atualizar.
            bloqueado_ate: fim do bloqueio, ou None para liberar.
        """
        usuario.bloqueado_ate = bloqueado_ate
        self._session.flush()

    def registrar_login(self, usuario: Usuario, *, agora: datetime) -> None:
        """Registra o instante do último login bem-sucedido.

        Args:
            usuario: usuário autenticado.
            agora: instante do login.
        """
        usuario.ultimo_login_em = agora
        self._session.flush()
