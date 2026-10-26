"""Criação de operadores e autorização para gestão de contas."""

from sqlalchemy.orm import Session

from src.entities import Usuario
from src.entities.papel import PapelUsuario
from src.repositories import UsuarioRepository
from src.repositories.exceptions import ErroDeDominio
from src.services.auditoria import registrar_evento
from src.services.autenticacao import normalizar_email
from src.services.senhas import ServicoDeSenhas, validar_politica


class AcessoNegado(ErroDeDominio):
    """O papel atual da conta não permite gerenciar usuários."""


def exigir_gerente(usuario: Usuario) -> None:
    """Autoriza a gestão pelo papel consultado no banco e audita recusas."""
    if usuario.papel != PapelUsuario.GERENTE:
        registrar_evento("acesso_negado", usuario_id=usuario.id)
        raise AcessoNegado


class ServicoDeUsuarios:
    """Cria operadores sem permitir atribuição de privilégios pela API."""

    def __init__(self, session: Session, senhas: ServicoDeSenhas) -> None:
        """Compartilha a transação do chamador e o serviço de hash existente."""
        self._usuarios = UsuarioRepository(session)
        self._senhas = senhas

    def criar_operador(
        self, criador: Usuario, *, email: str, nome: str, senha: str
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
            email=email, nome=nome, senha_hash=self._senhas.gerar_hash(senha)
        )
        registrar_evento(
            "conta_criada", usuario_id=usuario.id, criado_por_id=criador.id
        )
        return usuario
