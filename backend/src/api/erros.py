"""Tipos e handlers para devolver erros HTTP no formato padronizado da API."""

from collections.abc import Mapping
from enum import StrEnum
from logging import getLogger
from types import MappingProxyType
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

logger = getLogger(__name__)
ORIGENS_LOCALIZACAO_VALIDACAO = frozenset({"body", "query", "path", "header", "cookie"})


class CodigoErro(StrEnum):
    """Códigos estáveis usados pelos clientes para interpretar erros da API."""

    ARMADILHA_NAO_ENCONTRADA = "ARMADILHA_NAO_ENCONTRADA"
    ANALISE_NAO_ENCONTRADA = "ANALISE_NAO_ENCONTRADA"
    REFIL_ATIVO_INEXISTENTE = "REFIL_ATIVO_INEXISTENTE"
    IDENTIFICADOR_DUPLICADO = "IDENTIFICADOR_DUPLICADO"
    ARQUIVO_AUSENTE = "ARQUIVO_AUSENTE"
    FORMATO_NAO_SUPORTADO = "FORMATO_NAO_SUPORTADO"
    RESOLUCAO_INSUFICIENTE = "RESOLUCAO_INSUFICIENTE"
    ARQUIVO_MUITO_GRANDE = "ARQUIVO_MUITO_GRANDE"
    VALIDACAO_FALHOU = "VALIDACAO_FALHOU"
    REQUISICAO_INVALIDA = "REQUISICAO_INVALIDA"
    PLACA_NAO_DETECTADA = "PLACA_NAO_DETECTADA"
    FALHA_INFERENCIA = "FALHA_INFERENCIA"
    ROTA_NAO_ENCONTRADA = "ROTA_NAO_ENCONTRADA"
    METODO_NAO_PERMITIDO = "METODO_NAO_PERMITIDO"
    ERRO_INTERNO = "ERRO_INTERNO"


STATUS_HTTP_POR_CODIGO: Mapping[CodigoErro, int] = MappingProxyType(
    {
        CodigoErro.ARMADILHA_NAO_ENCONTRADA: 404,
        CodigoErro.ANALISE_NAO_ENCONTRADA: 404,
        CodigoErro.REFIL_ATIVO_INEXISTENTE: 409,
        CodigoErro.IDENTIFICADOR_DUPLICADO: 409,
        CodigoErro.ARQUIVO_AUSENTE: 400,
        CodigoErro.FORMATO_NAO_SUPORTADO: 400,
        CodigoErro.RESOLUCAO_INSUFICIENTE: 400,
        CodigoErro.ARQUIVO_MUITO_GRANDE: 413,
        CodigoErro.VALIDACAO_FALHOU: 422,
        CodigoErro.REQUISICAO_INVALIDA: 400,
        CodigoErro.PLACA_NAO_DETECTADA: 500,
        CodigoErro.FALHA_INFERENCIA: 500,
        CodigoErro.ROTA_NAO_ENCONTRADA: 404,
        CodigoErro.METODO_NAO_PERMITIDO: 405,
        CodigoErro.ERRO_INTERNO: 500,
    }
)


class ErroDeApi(Exception):
    """Falha de API com código estável e mensagem segura para exibição."""

    def __init__(
        self,
        codigo: CodigoErro,
        mensagem: str,
        detalhes: dict[str, Any] | None = None,
    ) -> None:
        """Armazena o erro sem aceitar um status HTTP independente do código.

        Args:
            codigo: código estável definido pela API.
            mensagem: texto em português que pode ser exibido ao usuário.
            detalhes: contexto adicional que pode ser omitido da resposta.
        """
        self.codigo = CodigoErro(codigo)
        self.mensagem = mensagem
        self.detalhes = None if detalhes is None else dict(detalhes)
        super().__init__(mensagem)

    @property
    def status_http(self) -> int:
        """Devolve o status associado ao código no mapeamento único da API."""
        return STATUS_HTTP_POR_CODIGO[self.codigo]


class ErroPadrao(BaseModel):
    """Representa os campos de erro que aparecem dentro da resposta JSON."""

    codigo: CodigoErro
    mensagem: str
    detalhes: dict[str, Any] | None = None


class RespostaErro(BaseModel):
    """Modelo da resposta pública de erro usada também na documentação OpenAPI."""

    erro: ErroPadrao


def registrar_handlers(app: FastAPI) -> None:
    """Registra handlers HTTP e captura falhas antes da camada de CORS.

    Args:
        app: aplicação FastAPI que receberá os handlers.
    """

    async def tratar_erro_de_api(_request: Request, exc: ErroDeApi) -> JSONResponse:
        return _resposta_erro(exc.codigo, exc.mensagem, exc.detalhes)

    async def tratar_validacao(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return _resposta_erro(
            CodigoErro.VALIDACAO_FALHOU,
            "A requisição contém campos inválidos.",
            _detalhes_validacao(exc),
        )

    async def tratar_erro_http(
        _request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        if exc.status_code == 404:
            return _resposta_erro(
                CodigoErro.ROTA_NAO_ENCONTRADA,
                "A rota solicitada não foi encontrada.",
            )
        if exc.status_code == 405:
            allow = next(
                (
                    valor
                    for nome, valor in (exc.headers or {}).items()
                    if nome.lower() == "allow"
                ),
                None,
            )
            headers = {"Allow": allow} if allow is not None else None
            return _resposta_erro(
                CodigoErro.METODO_NAO_PERMITIDO,
                "O método HTTP não é permitido para esta rota.",
                headers=headers,
            )
        if exc.status_code == 413:
            return _resposta_erro(
                CodigoErro.ARQUIVO_MUITO_GRANDE,
                "O arquivo enviado excede o tamanho permitido.",
            )
        if 400 <= exc.status_code < 500:
            return _resposta_erro(
                CodigoErro.REQUISICAO_INVALIDA,
                "A requisição não pôde ser processada.",
            )
        return _resposta_erro(
            CodigoErro.ERRO_INTERNO,
            "Ocorreu um erro interno. Tente novamente mais tarde.",
        )

    async def tratar_excecao_inesperada(
        _request: Request,
        exc: Exception,
    ) -> JSONResponse:
        return _resposta_erro_interno(exc)

    app.add_exception_handler(ErroDeApi, tratar_erro_de_api)
    app.add_exception_handler(RequestValidationError, tratar_validacao)
    app.add_exception_handler(StarletteHTTPException, tratar_erro_http)
    app.add_exception_handler(Exception, tratar_excecao_inesperada)
    app.add_middleware(_MiddlewareExcecoesApi)


def _detalhes_validacao(exc: RequestValidationError) -> dict[str, Any]:
    """Extrai nomes de campo e tipos sem copiar valores fornecidos pelo cliente."""
    campos_invalidos: list[dict[str, str]] = []
    # O retorno pode conter a entrada original; a resposta copia só localização e tipo.
    for erro in exc.errors():
        localizacao = erro.get("loc", ())
        if localizacao and localizacao[0] in ORIGENS_LOCALIZACAO_VALIDACAO:
            localizacao = localizacao[1:]
        partes = [str(parte) for parte in localizacao if isinstance(parte, (str, int))]
        campos_invalidos.append(
            {
                "campo": ".".join(partes) or "requisição",
                "tipo": str(erro.get("type", "invalid")),
            }
        )

    return {"campos_invalidos": campos_invalidos}


def _resposta_erro(
    codigo: CodigoErro,
    mensagem: str,
    detalhes: dict[str, Any] | None = None,
    *,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Serializa a resposta omitindo detalhes quando não foram informados."""
    resposta = RespostaErro(
        erro=ErroPadrao(codigo=codigo, mensagem=mensagem, detalhes=detalhes)
    )
    return JSONResponse(
        status_code=STATUS_HTTP_POR_CODIGO[codigo],
        content=resposta.model_dump(mode="json", exclude_none=True),
        headers=dict(headers) if headers is not None else None,
    )


def _resposta_erro_interno(exc: Exception) -> JSONResponse:
    """Registra o traceback completo e devolve somente a mensagem genérica."""
    logger.exception(
        "Erro inesperado ao processar a requisição.",
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return _resposta_erro(
        CodigoErro.ERRO_INTERNO,
        "Ocorreu um erro interno. Tente novamente mais tarde.",
    )


class _MiddlewareExcecoesApi(BaseHTTPMiddleware):
    """Converte falhas inesperadas para que a resposta atravesse o CORS."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Registra a falha no servidor e devolve a resposta genérica da API."""
        try:
            return await call_next(request)
        except Exception as exc:
            return _resposta_erro_interno(exc)


def respostas_de_erro(*codigos: CodigoErro) -> dict[str, dict[str, Any]]:
    """Devolve respostas OpenAPI apenas para os códigos declarados pela rota.

    Args:
        *codigos: códigos de erro que a operação pode devolver.
    """
    codigos_por_status: dict[int, list[CodigoErro]] = {}
    for codigo in codigos:
        codigos_por_status.setdefault(STATUS_HTTP_POR_CODIGO[codigo], []).append(codigo)

    return {
        str(status): {
            "model": RespostaErro,
            "description": "Códigos possíveis: "
            + ", ".join(codigo.value for codigo in codigos_do_status),
        }
        for status, codigos_do_status in codigos_por_status.items()
    }
