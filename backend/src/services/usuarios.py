"""Gestão de operadores e autorização de contas."""

from uuid import UUID

from sqlalchemy.orm import Session

from src.entities import Usuario
from src.entities.papel import PapelUsuario
from src.repositories import SessaoRepository, UsuarioRepository
from src.repositories.exceptions import ErroDeDominio
from src.services.auditoria import registrar_evento
from src.services.autenticacao import normalizar_email
from src.services.senhas import ServicoDeSenhas, validar_politica


class AcessoNegado(ErroDeDominio):
    """O papel atual da conta não permite gerenciar usuários."""


class ContaNaoEncontrada(ErroDeDominio):
    """A conta solicitada para remoção não existe."""


def exigir_gerente(usuario: Usuario) -> None:
    """Autoriza a gestão pelo papel consultado no banco e audita recusas."""
    if usuario.papel != PapelUsuario.GERENTE:
        registrar_evento("acesso_negado", usuario_id=usuario.id)
        raise AcessoNegado


class ServicoDeUsuarios:
    """Cria e exclui operadores sem permitir atribuição de privilégios pela API."""

    def __init__(self, session: Session) -> None:
        """Compartilha a transação do chamador entre contas e sessões."""
        self._usuarios = UsuarioRepository(session)
        self._sessoes = SessaoRepository(session)

    def criar_operador(
        self,
        criador: Usuario,
        *,
        senhas: ServicoDeSenhas,
        email: str,
        nome: str,
        senha: str,
    ) -> Usuario:
        """Valida a senha inicial, cria conta ativa e registra o autor.

        Raises:
            AcessoNegado: Se o criador não for gerente.
            SenhaFraca: Se a senha violar a política.
            EmailDuplicado: Se o endereço normalizado já estiver cadastrado.
        """
        exigir_gerente(criador)
        email = normalizar_email(email)
        validar_politica(senha, email=email, nome=nome)
        usuario = self._usuarios.create(
            email=email,
            nome=nome,
            senha_hash=senhas.gerar_hash(senha),
            troca_senha_pendente=True,
        )
        registrar_evento(
            "conta_criada", usuario_id=usuario.id, criado_por_id=criador.id
        )
        return usuario

    def excluir_operador(self, gerente: Usuario, usuario_id: UUID) -> UUID:
        """Exclui um operador e suas sessões na transação atual.

        Raises:
            AcessoNegado: se a conta solicitante não for gerente atual ou se o
                alvo não for um operador diferente do próprio gerente.
            ContaNaoEncontrada: se o UUID não identificar uma conta.
        """
        gerente_atual = self._usuarios.get_by_id_for_update(gerente.id)
        if gerente_atual is None:
            registrar_evento("acesso_negado", usuario_id=gerente.id)
            raise AcessoNegado
        exigir_gerente(gerente_atual)

        usuario = self._usuarios.get_by_id_for_update(usuario_id)
        if usuario is None:
            raise ContaNaoEncontrada
        if usuario.id == gerente_atual.id or usuario.papel != PapelUsuario.OPERADOR:
            registrar_evento(
                "acesso_negado",
                usuario_id=gerente_atual.id,
                motivo="exclusao_conta_nao_permitida",
            )
            raise AcessoNegado

        self._sessoes.apagar_do_usuario(usuario.id)
        self._usuarios.delete(usuario)
        return usuario.id
