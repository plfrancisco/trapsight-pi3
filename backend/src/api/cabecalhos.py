"""Cabeçalhos de segurança que a própria API acrescenta às respostas."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]
ASGIApp = Callable[[dict[str, Any], Receive, Send], Awaitable[None]]

_PREFIXO_AUTENTICACAO = "/api/auth/"


class CabecalhosDeSegurancaMiddleware:
    """Acrescenta `nosniff` a tudo e `no-store` às respostas de autenticação.

    O proxy reverso repete esses cabeçalhos em produção; a API os envia por
    conta própria para não depender de quem está na frente dela.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Guarda a próxima camada ASGI.

        Args:
            app: próxima camada da pilha HTTP.
        """
        self._app = app

    async def __call__(
        self, scope: dict[str, Any], receive: Receive, send: Send
    ) -> None:
        """Injeta os cabeçalhos na mensagem de início da resposta.

        Args:
            scope: metadados ASGI da requisição.
            receive: fonte dos blocos recebidos do cliente.
            send: destino das mensagens da resposta.
        """
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        sem_cache = scope.get("path", "").startswith(_PREFIXO_AUTENTICACAO)
        # O Cache-Control só é substituído nas rotas de autenticação: o das imagens
        # de análise (privado e imutável) precisa seguir intacto.
        substituidos = {b"x-content-type-options"} | (
            {b"cache-control"} if sem_cache else set()
        )

        async def enviar(mensagem: dict[str, Any]) -> None:
            if mensagem["type"] == "http.response.start":
                cabecalhos = [
                    (nome, valor)
                    for nome, valor in mensagem.get("headers", [])
                    if nome.lower() not in substituidos
                ]
                cabecalhos.append((b"x-content-type-options", b"nosniff"))
                if sem_cache:
                    cabecalhos.append((b"cache-control", b"no-store"))
                mensagem = {**mensagem, "headers": cabecalhos}
            await send(mensagem)

        await self._app(scope, receive, enviar)
