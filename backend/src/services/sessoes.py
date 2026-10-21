"""Criação, validação e revogação de sessões autenticadas."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from src.config.settings import Settings
from src.entities import Sessao, Usuario
from src.repositories import SessaoRepository, UsuarioRepository
from src.services.auditoria import registrar_evento

# Intervalo máximo entre gravações do último uso, para não escrever a cada requisição.
_RENOVACAO_MAXIMA_SEGUNDOS = 60


def gerar_token() -> str:
    """Gera um token de sessão de 256 bits, seguro para cookie.

    Returns:
        Token aleatório em base64 de URL, sem qualquer informação embutida.
    """
    return secrets.token_urlsafe(32)


def gerar_token_csrf() -> str:
    """Gera o token CSRF sincronizado com a sessão.

    Returns:
        Token aleatório em base64 de URL.
    """
    return secrets.token_urlsafe(32)


def hash_do_token(token: str) -> str:
    """Calcula o SHA-256 do token: só ele é gravado, nunca o token em claro.

    Args:
        token: token apresentado pelo navegador.

    Returns:
        Resumo hexadecimal de 64 caracteres.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SessaoValida:
    """Sessão aprovada, com o usuário dono dela."""

    sessao: Sessao
    usuario: Usuario


class ServicoDeSessoes:
    """Regras de ciclo de vida da sessão: expiração, limite e revogação."""

    def __init__(self, session: Session, settings: Settings) -> None:
        """Prepara os repositórios sobre a transação do chamador.

        Args:
            session: sessão SQLAlchemy cuja transação o chamador controla.
            settings: configuração com prazos e limites.
        """
        self._settings = settings
        self._sessoes = SessaoRepository(session)
        self._usuarios = UsuarioRepository(session)

    def criar(
        self,
        usuario: Usuario,
        *,
        agora: datetime,
        ip: str | None,
        user_agent: str | None,
    ) -> tuple[Sessao, str]:
        """Abre uma sessão nova (token inédito) e respeita o limite por usuário.

        Args:
            usuario: dono da sessão.
            agora: instante de criação.
            ip: endereço de origem.
            user_agent: agente do navegador.

        Returns:
            A sessão persistida e o token em claro, que só existe neste retorno.
        """
        self._sessoes.apagar_expiradas(agora=agora)
        abertas = [
            sessao
            for sessao in self._sessoes.list_abertas(usuario.id)
            if self._esta_ativa(sessao, agora)
        ]
        excesso = len(abertas) - self._settings.sessao_maxima_por_usuario + 1
        for sessao in abertas[: max(excesso, 0)]:
            self._sessoes.revogar(sessao, agora=agora)
            registrar_evento("sessao_revogada", usuario_id=usuario.id, motivo="limite")

        token = gerar_token()
        sessao = self._sessoes.create(
            usuario_id=usuario.id,
            token_hash=hash_do_token(token),
            csrf_token=gerar_token_csrf(),
            expira_em=agora
            + timedelta(seconds=self._settings.sessao_duracao_maxima_segundos),
            agora=agora,
            ip=ip,
            user_agent=user_agent,
        )
        return sessao, token

    def validar(self, token: str, *, agora: datetime) -> SessaoValida | None:
        """Valida o token e renova o último uso, de forma limitada.

        Args:
            token: token apresentado pelo navegador.
            agora: instante de referência.

        Returns:
            A sessão e o usuário, ou None se o token não vale (desconhecido,
            revogado, expirado, inativo ou de conta desativada).
        """
        sessao = self._sessoes.get_by_token_hash(hash_do_token(token))
        if sessao is None or not self._esta_ativa(sessao, agora):
            return None
        usuario = self._usuarios.get_by_id(sessao.usuario_id)
        if usuario is None or not usuario.ativo:
            return None

        if agora - sessao.ultimo_uso_em >= self._intervalo_de_renovacao():
            self._sessoes.tocar_uso(sessao, agora=agora)
        return SessaoValida(sessao=sessao, usuario=usuario)

    def revogar(self, sessao: Sessao, *, agora: datetime) -> None:
        """Revoga a sessão no servidor (apagar só o cookie não invalidaria o token).

        Args:
            sessao: sessão a revogar.
            agora: instante da revogação.
        """
        self._sessoes.revogar(sessao, agora=agora)

    def revogar_todas(
        self, usuario: Usuario, *, agora: datetime, exceto: Sessao | None = None
    ) -> int:
        """Revoga todas as sessões abertas do usuário.

        Args:
            usuario: dono das sessões.
            agora: instante da revogação.
            exceto: sessão a preservar, quando houver.

        Returns:
            Quantidade de sessões revogadas.
        """
        return self._sessoes.revogar_todas(
            usuario.id, agora=agora, exceto=None if exceto is None else exceto.id
        )

    def _esta_ativa(self, sessao: Sessao, agora: datetime) -> bool:
        if sessao.revogada_em is not None or agora >= sessao.expira_em:
            return False
        inatividade = timedelta(seconds=self._settings.sessao_inatividade_segundos)
        return agora - sessao.ultimo_uso_em < inatividade

    def _intervalo_de_renovacao(self) -> timedelta:
        """Um quinto do prazo de inatividade, no máximo um minuto."""
        segundos = min(
            _RENOVACAO_MAXIMA_SEGUNDOS,
            max(1, self._settings.sessao_inatividade_segundos // 5),
        )
        return timedelta(seconds=segundos)
