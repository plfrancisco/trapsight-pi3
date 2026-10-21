"""Cookie de sessão e verificação de origem, compartilhados pelo middleware e pelas rotas."""

from __future__ import annotations

from urllib.parse import urlsplit

from starlette.requests import Request
from starlette.responses import Response

from src.config.settings import Settings

NOME_DO_COOKIE_SEGURO = "__Host-trapsight_sessao"
NOME_DO_COOKIE_DESENVOLVIMENTO = "trapsight_sessao"
CABECALHO_CSRF = "x-csrf-token"


def nome_do_cookie(settings: Settings) -> str:
    """Devolve o nome do cookie de sessão.

    O prefixo `__Host-` exige `Secure`, `Path=/` e proíbe `Domain`, então só é
    usado quando o cookie é seguro (em desenvolvimento local sem HTTPS não vale).

    Args:
        settings: configuração com o modo do cookie.

    Returns:
        Nome do cookie de sessão.
    """
    if settings.cookie_seguro:
        return NOME_DO_COOKIE_SEGURO
    return NOME_DO_COOKIE_DESENVOLVIMENTO


def definir_cookie(resposta: Response, settings: Settings, token: str) -> None:
    """Grava o cookie de sessão: `HttpOnly`, `SameSite=Strict`, sem `Domain`.

    O cookie é de sessão (sem `Max-Age` nem `Expires`): os prazos são aplicados
    pelo servidor, que não depende do cookie para expirar a sessão.

    Args:
        resposta: resposta que carregará o `Set-Cookie`.
        settings: configuração com o modo do cookie.
        token: token de sessão em claro.
    """
    resposta.set_cookie(
        key=nome_do_cookie(settings),
        value=token,
        httponly=True,
        secure=settings.cookie_seguro,
        samesite="strict",
        path="/",
    )


def apagar_cookie(resposta: Response, settings: Settings) -> None:
    """Pede ao navegador que descarte o cookie de sessão.

    Args:
        resposta: resposta que carregará o `Set-Cookie`.
        settings: configuração com o modo do cookie.
    """
    resposta.delete_cookie(
        key=nome_do_cookie(settings),
        path="/",
        secure=settings.cookie_seguro,
        httponly=True,
        samesite="strict",
    )


def origem_da_requisicao(request: Request) -> str | None:
    """Obtém a origem pelo cabeçalho `Origin` ou, na falta dele, pelo `Referer`.

    Args:
        request: requisição recebida.

    Returns:
        Origem no formato `esquema://host[:porta]`, ou None se não houver.
    """
    origem = request.headers.get("origin")
    if origem:
        return origem
    referencia = request.headers.get("referer")
    if not referencia:
        return None
    partes = urlsplit(referencia)
    if not partes.scheme or not partes.netloc:
        return None
    return f"{partes.scheme}://{partes.netloc}"


def origem_permitida(request: Request, settings: Settings) -> bool:
    """Confere se a origem coincide com uma das origens configuradas.

    Ausente ou `null` é recusado: um site hostil pode forjar uma requisição sem
    origem identificável.

    Args:
        request: requisição recebida.
        settings: configuração com `cors_origens`.

    Returns:
        Verdadeiro somente para origens exatamente iguais às permitidas.
    """
    origem = origem_da_requisicao(request)
    return origem is not None and origem != "null" and origem in settings.cors_origens
