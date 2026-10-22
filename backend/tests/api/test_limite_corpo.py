"""Testes do middleware que rejeita corpos grandes antes da rota."""

import asyncio
from typing import Annotated

from fastapi import Body, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import Message, Scope

from src.api.limite_corpo import LIMITE_CORPO_ANALISE_BYTES, LimiteCorpoMiddleware


def _criar_app(contador: dict[str, int]) -> FastAPI:
    """Cria uma rota que só é chamada depois que o corpo foi lido pelo framework."""
    app = FastAPI()

    @app.post("/api/analises")
    async def analisar(corpo: Annotated[bytes, Body()]) -> dict[str, int]:
        contador["chamadas"] += 1
        return {"bytes": len(corpo)}

    app.add_middleware(LimiteCorpoMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["POST"],
        allow_headers=["Content-Type"],
    )
    return app


def _scope(headers: list[tuple[bytes, bytes]]) -> Scope:
    """Monta o mínimo de metadados ASGI para uma chamada HTTP de teste."""
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/analises",
        "raw_path": b"/api/analises",
        "query_string": b"",
        "root_path": "",
        "headers": headers,
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
    }


def _chamar_app(
    app: FastAPI,
    headers: list[tuple[bytes, bytes]],
    blocos: list[bytes],
) -> tuple[list[Message], int]:
    """Executa ASGI com um fluxo controlado e devolve mensagens e leituras."""
    mensagens: list[Message] = []
    quantidade_leituras = 0
    proximo_bloco = iter(blocos)

    async def receber() -> Message:
        nonlocal quantidade_leituras
        quantidade_leituras += 1
        try:
            bloco = next(proximo_bloco)
        except StopIteration:
            return {"type": "http.request", "body": b"", "more_body": False}
        return {
            "type": "http.request",
            "body": bloco,
            "more_body": bool(blocos),
        }

    async def enviar(mensagem: Message) -> None:
        mensagens.append(mensagem)

    asyncio.run(app(_scope(headers), receber, enviar))
    return mensagens, quantidade_leituras


def _resposta(mensagens: list[Message]) -> tuple[int, dict[bytes, bytes], bytes]:
    """Extrai status, cabeçalhos e corpo de uma resposta ASGI simples."""
    inicio = next(msg for msg in mensagens if msg["type"] == "http.response.start")
    corpo = b"".join(
        msg.get("body", b"") for msg in mensagens if msg["type"] == "http.response.body"
    )
    return (
        int(inicio["status"]),
        dict(inicio.get("headers", [])),
        corpo,
    )


def test_content_length_acima_do_limite_rejeita_sem_ler_nem_chamar_rota() -> None:
    contador = {"chamadas": 0}
    app = _criar_app(contador)
    mensagens, leituras = _chamar_app(
        app,
        [
            (b"content-length", str(LIMITE_CORPO_ANALISE_BYTES + 1).encode()),
            (b"origin", b"http://localhost:5173"),
        ],
        [],
    )

    status, cabecalhos, conteudo = _resposta(mensagens)
    assert status == 413
    assert b"ARQUIVO_MUITO_GRANDE" in conteudo
    assert cabecalhos[b"access-control-allow-origin"] == b"http://localhost:5173"
    assert leituras == 0
    assert contador["chamadas"] == 0


def test_corpo_em_stream_sem_content_length_rejeita_antes_de_chamar_rota() -> None:
    contador = {"chamadas": 0}
    app = _criar_app(contador)
    mensagens, _leituras = _chamar_app(
        app,
        [(b"origin", b"http://localhost:5173")],
        [b"x" * LIMITE_CORPO_ANALISE_BYTES, b"x"],
    )

    status, cabecalhos, conteudo = _resposta(mensagens)
    assert status == 413
    assert b"ARQUIVO_MUITO_GRANDE" in conteudo
    assert cabecalhos[b"access-control-allow-origin"] == b"http://localhost:5173"
    assert contador["chamadas"] == 0
