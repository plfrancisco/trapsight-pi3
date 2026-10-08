"""Limita o corpo multipart antes que o parser crie o arquivo da requisição."""

from collections.abc import Awaitable, Callable
from typing import Any

from starlette.responses import JSONResponse

from src.api.erros import CodigoErro
from src.services.upload import LIMITE_TAMANHO_UPLOAD_BYTES

# Um MiB cobre boundaries e cabeçalhos multipart sem permitir campos extras grandes.
SOBRECARGA_MULTIPART_BYTES = 1024 * 1024
LIMITE_CORPO_ANALISE_BYTES = LIMITE_TAMANHO_UPLOAD_BYTES + SOBRECARGA_MULTIPART_BYTES
_MENSAGEM_CORPO_GRANDE = "O arquivo enviado excede o tamanho permitido."

ASGIApp = Callable[
    [dict[str, Any], Callable[..., Awaitable[Any]], Callable[..., Awaitable[Any]]],
    Awaitable[None],
]


class _CorpoAcimaDoLimite(Exception):
    """Interrompe a leitura multipart assim que o teto de bytes é ultrapassado."""


class LimiteCorpoMiddleware:
    """Conta o corpo apenas na rota de análise e padroniza rejeições por tamanho."""

    def __init__(self, app: ASGIApp) -> None:
        """Guarda a aplicação ASGI que receberá requisições abaixo do limite.

        Args:
            app: próxima camada ASGI da pilha HTTP.
        """
        self._app = app

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[..., Awaitable[Any]],
        send: Callable[..., Awaitable[Any]],
    ) -> None:
        """Rejeita tamanho declarado ou medido sem acumular o corpo multipart.

        Args:
            scope: metadados ASGI da requisição.
            receive: fonte dos blocos recebidos do cliente.
            send: destino das mensagens da resposta.
        """
        if (
            scope["type"] != "http"
            or scope.get("path") != "/api/analises"
            or scope.get("method") != "POST"
        ):
            await self._app(scope, receive, send)
            return

        tamanho_declarado = self._tamanho_declarado(scope.get("headers", []))
        if (
            tamanho_declarado is not None
            and tamanho_declarado > LIMITE_CORPO_ANALISE_BYTES
        ):
            await self._enviar_erro(scope, receive, send)
            return

        total = 0
        excedeu_limite = False
        # A rota POST de análise só responde JSON pequeno. Retemos essas mensagens
        # para descartar o 400 que o parser multipart do FastAPI pode gerar ao
        # capturar a exceção de receive e emitir o 413 padronizado do middleware.
        respostas: list[dict[str, Any]] = []

        async def receber_limitado() -> dict[str, Any]:
            nonlocal total, excedeu_limite
            mensagem = await receive()
            if mensagem["type"] == "http.request":
                total += len(mensagem.get("body", b""))
                if total > LIMITE_CORPO_ANALISE_BYTES:
                    # O parser multipart transforma a exceção em 400; a flag,
                    # setada antes do raise, permite ao middleware substituir por 413.
                    excedeu_limite = True
                    raise _CorpoAcimaDoLimite
            return mensagem

        async def capturar_resposta(mensagem: dict[str, Any]) -> None:
            respostas.append(mensagem)

        try:
            await self._app(scope, receber_limitado, capturar_resposta)
        except _CorpoAcimaDoLimite:
            excedeu_limite = True

        if excedeu_limite:
            await self._enviar_erro(scope, receive, send)
            return

        for mensagem in respostas:
            await send(mensagem)

    @staticmethod
    def _tamanho_declarado(headers: list[tuple[bytes, bytes]]) -> int | None:
        """Lê Content-Length sem confiar nele como única defesa de tamanho."""
        valores = [
            valor for nome, valor in headers if nome.lower() == b"content-length"
        ]
        if not valores:
            return None
        try:
            tamanhos = [int(valor) for valor in valores]
        except ValueError:
            return None
        return max(tamanhos) if all(tamanho >= 0 for tamanho in tamanhos) else None

    @staticmethod
    async def _enviar_erro(
        scope: dict[str, Any],
        receive: Callable[..., Awaitable[Any]],
        send: Callable[..., Awaitable[Any]],
    ) -> None:
        """Devolve o mesmo envelope público de erros usado pelos handlers da API."""
        resposta = JSONResponse(
            status_code=413,
            content={
                "erro": {
                    "codigo": CodigoErro.ARQUIVO_MUITO_GRANDE.value,
                    "mensagem": _MENSAGEM_CORPO_GRANDE,
                }
            },
        )
        await resposta(scope, receive, send)
