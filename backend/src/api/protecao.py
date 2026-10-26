"""Middleware que exige sessão, CSRF e origem antes de o corpo ser lido.

No FastAPI o corpo da requisição é lido ANTES das dependências das rotas; uma
proteção apenas por dependência deixaria um anônimo enviar um upload inteiro
antes de receber 401. Por isso a verificação acontece aqui, na camada ASGI, e
vale para toda rota sob `/api`, inclusive as que ainda serão criadas.
"""

from __future__ import annotations

import hmac
from collections.abc import Awaitable, Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import FastAPI
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import Response

from src.api.erros import CodigoErro, resposta_de_erro, resposta_de_erro_interno
from src.api.sessao_http import (
    CABECALHO_CSRF,
    apagar_cookie,
    nome_do_cookie,
    origem_permitida,
)
from src.config.settings import Settings
from src.entities.papel import PapelUsuario
from src.services.sessoes import ServicoDeSessoes

ROTA_DE_LOGIN = "/api/auth/login"
ROTA_DE_ANALISE = "/api/analises"
METODOS_SEGUROS = frozenset({"GET", "HEAD", "OPTIONS"})
_CABECALHOS_SEM_CACHE = {"Cache-Control": "no-store"}
_OPERACOES_COM_TROCA_PENDENTE = frozenset(
    {
        ("GET", "/api/auth/me"),
        ("POST", "/api/auth/senha"),
        ("POST", "/api/auth/logout"),
    }
)

Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]
ASGIApp = Callable[[dict[str, Any], Receive, Send], Awaitable[None]]


@dataclass(frozen=True)
class SessaoAutenticada:
    """Dados da sessão aprovada, em tipos simples (a transação já foi encerrada)."""

    sessao_id: UUID
    usuario_id: UUID
    email: str
    nome: str
    papel: PapelUsuario
    troca_senha_pendente: bool
    csrf_token: str


def agora_utc() -> datetime:
    """Relógio padrão da aplicação, substituível em `app.state.relogio`.

    Returns:
        Instante atual com fuso UTC.
    """
    return datetime.now(timezone.utc)


def abrir_sessao(aplicacao: FastAPI) -> AbstractContextManager[Session]:
    """Abre uma sessão de banco para o middleware.

    O ponto de extensão `app.state.provedor_de_sessao` devolve um gerenciador de
    contexto de sessão; a aplicação o define com a fábrica real e os testes o
    substituem por uma sessão transacional descartável.

    Args:
        aplicacao: aplicação que guarda o provedor de sessões.

    Returns:
        Gerenciador de contexto que entrega a sessão e a fecha ao final.
    """
    return aplicacao.state.provedor_de_sessao()


def _validar_sessao(
    aplicacao: FastAPI, settings: Settings, token: str
) -> SessaoAutenticada | None:
    """Valida o token no banco e confirma a renovação do último uso."""
    with abrir_sessao(aplicacao) as session:
        valida = ServicoDeSessoes(session, settings).validar(
            token, agora=aplicacao.state.relogio()
        )
        if valida is None:
            return None
        autenticada = SessaoAutenticada(
            sessao_id=valida.sessao.id,
            usuario_id=valida.usuario.id,
            email=valida.usuario.email,
            nome=valida.usuario.nome,
            papel=valida.usuario.papel,
            troca_senha_pendente=valida.usuario.troca_senha_pendente,
            csrf_token=valida.sessao.csrf_token,
        )
        session.commit()
        return autenticada


class ProtecaoDeSessaoMiddleware:
    """Recusa, antes de ler o corpo, o que não tem sessão, CSRF ou origem válidos."""

    def __init__(self, app: ASGIApp) -> None:
        """Guarda a próxima camada ASGI.

        Args:
            app: próxima camada da pilha HTTP.
        """
        self._app = app

    async def __call__(
        self, scope: dict[str, Any], receive: Receive, send: Send
    ) -> None:
        """Decide se a requisição segue para as rotas.

        Args:
            scope: metadados ASGI da requisição.
            receive: fonte dos blocos recebidos do cliente.
            send: destino das mensagens da resposta.
        """
        caminho = scope.get("path", "")
        if (
            scope["type"] != "http"
            or not (caminho == "/api" or caminho.startswith("/api/"))
            or scope["method"] == "OPTIONS"
        ):
            await self._app(scope, receive, send)
            return

        try:
            recusa = await self._avaliar(scope)
        except Exception as erro:  # a falha do banco não pode vazar nem derrubar o CORS
            recusa = resposta_de_erro_interno(erro)
        if recusa is not None:
            await recusa(scope, receive, send)
            return
        await self._app(scope, receive, send)

    async def _avaliar(self, scope: dict[str, Any]) -> Response | None:
        """Devolve a resposta de recusa, ou None para a requisição seguir."""
        aplicacao: FastAPI = scope["app"]
        settings: Settings = aplicacao.state.settings
        request = Request(scope)
        metodo = scope["method"]
        metodo_altera_estado = metodo not in METODOS_SEGUROS

        if scope["path"] == ROTA_DE_LOGIN:
            # Ainda não há sessão, mas um site hostil não pode forçar o login.
            if metodo_altera_estado and not origem_permitida(request, settings):
                return _recusa_csrf()
            return None

        token = request.cookies.get(nome_do_cookie(settings))
        autenticada = (
            None
            if not token
            else await run_in_threadpool(_validar_sessao, aplicacao, settings, token)
        )
        if autenticada is None:
            resposta = resposta_de_erro(
                CodigoErro.NAO_AUTENTICADO,
                "Autenticação necessária.",
                headers=_CABECALHOS_SEM_CACHE,
            )
            if token:
                # Cookie vencido ou revogado: o navegador deve descartá-lo.
                apagar_cookie(resposta, settings)
            return resposta

        if metodo_altera_estado:
            enviado = request.headers.get(CABECALHO_CSRF, "")
            if not origem_permitida(request, settings) or not hmac.compare_digest(
                enviado.encode("utf-8"), autenticada.csrf_token.encode("utf-8")
            ):
                return _recusa_csrf()

        if (
            autenticada.troca_senha_pendente
            and (metodo, scope["path"]) not in _OPERACOES_COM_TROCA_PENDENTE
        ):
            return resposta_de_erro(
                CodigoErro.TROCA_DE_SENHA_OBRIGATORIA,
                "Troque a senha inicial antes de acessar o sistema.",
                headers=_CABECALHOS_SEM_CACHE,
            )

        if metodo == "POST" and scope["path"] == ROTA_DE_ANALISE:
            espera = aplicacao.state.limitador_de_analises.tentar(
                str(autenticada.usuario_id)
            )
            if espera is not None:
                return resposta_de_erro(
                    CodigoErro.LIMITE_ANALISES,
                    "Limite de análises por minuto atingido. Tente novamente em instantes.",
                    headers={"Retry-After": str(espera)},
                )

        scope.setdefault("state", {})["sessao_atual"] = autenticada
        return None


def _recusa_csrf() -> Response:
    return resposta_de_erro(
        CodigoErro.CSRF_INVALIDO,
        "A requisição foi recusada. Recarregue a página e tente novamente.",
        headers=_CABECALHOS_SEM_CACHE,
    )
