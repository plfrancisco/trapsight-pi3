"""Fluxos de login e de troca de senha, na ordem exigida por login.md (seção 6.2)."""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from src.config.settings import Settings
from src.entities import Sessao, Usuario
from src.repositories import (
    TentativaLoginRepository,
    UsuarioRepository,
)
from src.services.auditoria import registrar_evento
from src.services.senhas import ServicoDeSenhas, validar_politica
from src.services.sessoes import ServicoDeSessoes


class CredenciaisInvalidas(Exception):
    """Falha de login ou de confirmação de senha; não diz o motivo ao cliente."""


class LimiteDeTentativas(Exception):
    """O endereço excedeu o limite de falhas de login na janela."""

    def __init__(self, retry_after: int) -> None:
        """Guarda quanto o cliente deve esperar.

        Args:
            retry_after: segundos até uma nova tentativa fazer sentido.
        """
        super().__init__("Limite de tentativas excedido.")
        self.retry_after = retry_after


@dataclass(frozen=True)
class ResultadoDeLogin:
    """Sessão recém-criada: o token em claro só existe neste objeto."""

    usuario: Usuario
    sessao: Sessao
    token: str


def normalizar_email(email: str) -> str:
    """Normaliza o e-mail para comparação: NFKC, minúsculas e sem espaços nas pontas.

    A normalização NFKC impede que variantes visuais (largura total, ligaduras)
    criem contas distintas para o mesmo endereço.

    Args:
        email: e-mail como digitado.

    Returns:
        E-mail normalizado.
    """
    return unicodedata.normalize("NFKC", email).strip().lower()


def identificador_da_conta(email_normalizado: str) -> str:
    """Resume o e-mail para contar tentativas sem gravar o texto digitado.

    Args:
        email_normalizado: e-mail já normalizado.

    Returns:
        SHA-256 hexadecimal do e-mail.
    """
    return hashlib.sha256(email_normalizado.encode("utf-8")).hexdigest()


class ServicoDeAutenticacao:
    """Autentica contas, aplica bloqueios e abre sessões."""

    def __init__(
        self, session: Session, settings: Settings, senhas: ServicoDeSenhas
    ) -> None:
        """Prepara os repositórios e serviços sobre a transação do chamador.

        Args:
            session: sessão SQLAlchemy cuja transação o chamador controla.
            settings: configuração com limites e prazos.
            senhas: serviço de hash e verificação de senhas.
        """
        self._settings = settings
        self._senhas = senhas
        self._usuarios = UsuarioRepository(session)
        self._tentativas = TentativaLoginRepository(session)
        self._sessoes = ServicoDeSessoes(session, settings)

    def entrar(
        self,
        email: str,
        senha: str,
        *,
        ip: str,
        user_agent: str | None,
        agora: datetime,
    ) -> ResultadoDeLogin:
        """Autentica e abre uma sessão.

        A ordem evita enumerar contas: a verificação do Argon2 SEMPRE roda
        (contra um hash fictício se a conta não existe) e só depois se consulta
        se a conta está ativa ou bloqueada.

        O chamador precisa confirmar a transação também quando CredenciaisInvalidas
        é lançada, para preservar o registro da tentativa.

        Args:
            email: e-mail como digitado.
            senha: senha como digitada.
            ip: endereço de origem.
            user_agent: agente do navegador.
            agora: instante da tentativa.

        Returns:
            O usuário, a sessão e o token em claro.

        Raises:
            LimiteDeTentativas: se o IP excedeu o limite de falhas na janela.
            CredenciaisInvalidas: para qualquer falha de autenticação.
        """
        janela = agora - timedelta(seconds=self._settings.login_janela_segundos)
        if (
            self._tentativas.contar_falhas_por_ip(ip, desde=janela)
            >= self._settings.login_falhas_por_ip
        ):
            registrar_evento("login_limite_ip", ip=ip)
            raise LimiteDeTentativas(self._settings.login_janela_segundos)

        email_normalizado = normalizar_email(email)
        identificador = identificador_da_conta(email_normalizado)
        usuario = self._usuarios.get_by_email(email_normalizado)

        if usuario is None:
            self._senhas.verificar_contra_ficticio(senha)
            senha_confere, hash_novo = False, None
        else:
            senha_confere, hash_novo = self._senhas.verificar(senha, usuario.senha_hash)

        bloqueada = (
            usuario is not None
            and usuario.bloqueado_ate is not None
            and usuario.bloqueado_ate > agora
        )
        autenticado = (
            senha_confere and usuario is not None and usuario.ativo and not bloqueada
        )
        self._tentativas.registrar(
            identificador_hash=identificador, ip=ip, sucesso=autenticado, agora=agora
        )

        if not autenticado or usuario is None:
            self._registrar_falha(usuario, identificador, ip, bloqueada, agora, janela)
            raise CredenciaisInvalidas

        if hash_novo is not None:
            self._usuarios.regravar_hash(usuario, hash_novo)
        if usuario.bloqueado_ate is not None:
            self._usuarios.definir_bloqueio(usuario, None)
        self._usuarios.registrar_login(usuario, agora=agora)
        sessao, token = self._sessoes.criar(
            usuario, agora=agora, ip=ip, user_agent=user_agent
        )
        registrar_evento("login_ok", usuario_id=usuario.id, sessao_id=sessao.id, ip=ip)
        return ResultadoDeLogin(usuario=usuario, sessao=sessao, token=token)

    def trocar_senha(
        self,
        usuario: Usuario,
        *,
        senha_atual: str,
        senha_nova: str,
        ip: str | None,
        user_agent: str | None,
        agora: datetime,
    ) -> ResultadoDeLogin:
        """Troca a senha, encerra todas as sessões e abre uma nova.

        Args:
            usuario: usuário autenticado que pede a troca.
            senha_atual: senha em uso, para confirmar a identidade.
            senha_nova: nova senha, sujeita à política.
            ip: endereço de origem.
            user_agent: agente do navegador.
            agora: instante da troca.

        Returns:
            A sessão nova (as anteriores, inclusive a atual, ficam revogadas).

        Raises:
            CredenciaisInvalidas: se a senha atual estiver errada.
            SenhaFraca: se a nova senha violar a política.
        """
        confere, _ = self._senhas.verificar(senha_atual, usuario.senha_hash)
        if not confere:
            registrar_evento(
                "troca_senha_recusada", usuario_id=usuario.id, motivo="senha_atual"
            )
            raise CredenciaisInvalidas
        validar_politica(senha_nova, email=usuario.email, nome=usuario.nome)

        usuario.troca_senha_pendente = False
        self._usuarios.definir_senha_hash(
            usuario, self._senhas.gerar_hash(senha_nova), agora=agora
        )
        self._sessoes.revogar_todas(usuario, agora=agora)
        sessao, token = self._sessoes.criar(
            usuario, agora=agora, ip=ip, user_agent=user_agent
        )
        registrar_evento("senha_trocada", usuario_id=usuario.id, sessao_id=sessao.id)
        return ResultadoDeLogin(usuario=usuario, sessao=sessao, token=token)

    def _registrar_falha(
        self,
        usuario: Usuario | None,
        identificador: str,
        ip: str,
        ja_bloqueada: bool,
        agora: datetime,
        janela: datetime,
    ) -> None:
        """Audita a falha e bloqueia a conta ao atingir o limite (nunca em definitivo)."""
        registrar_evento(
            "login_falhou",
            usuario_id=None if usuario is None else usuario.id,
            ip=ip,
        )
        if usuario is None or ja_bloqueada:
            # Falhar durante o bloqueio não o estende: um terceiro não pode trancar
            # a conta para sempre.
            return
        falhas = self._tentativas.contar_falhas_por_conta(identificador, desde=janela)
        if falhas >= self._settings.login_falhas_por_conta:
            self._usuarios.definir_bloqueio(
                usuario,
                agora + timedelta(seconds=self._settings.login_bloqueio_segundos),
            )
            registrar_evento("login_bloqueado", usuario_id=usuario.id, ip=ip)
