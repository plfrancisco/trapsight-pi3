"""Endpoints de login, logout, sessão atual e troca de senha."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from src.api.dependencias import (
    get_relogio,
    get_servico_de_senhas,
    get_session,
    get_settings,
)
from src.api.erros import CodigoErro, ErroDeApi, respostas_de_erro
from src.api.protecao import SessaoAutenticada
from src.api.schemas.auth import (
    LoginEntrada,
    SessaoSaida,
    TrocaSenhaEntrada,
    TrocaSenhaSaida,
    UsuarioSaida,
)
from src.api.sessao_http import apagar_cookie, definir_cookie
from src.config.settings import Settings
from src.repositories import SessaoRepository, UsuarioRepository
from src.services.auditoria import registrar_evento
from src.services.autenticacao import (
    CredenciaisInvalidas,
    LimiteDeTentativas,
    ServicoDeAutenticacao,
)
from src.services.senhas import SenhaFraca, ServicoDeSenhas
from src.services.sessoes import ServicoDeSessoes

router = APIRouter(prefix="/auth", tags=["Autenticação"])

_MENSAGEM_CREDENCIAIS = "E-mail ou senha inválidos."
_TAMANHO_MAXIMO_USER_AGENT = 255


def get_sessao_autenticada(request: Request) -> SessaoAutenticada:
    """Obtém a sessão que o middleware de proteção aprovou para esta requisição.

    Args:
        request: requisição que já passou pela proteção de sessão.

    Returns:
        Dados da sessão autenticada.
    """
    return request.state.sessao_atual


def _ip(request: Request) -> str:
    """Endereço de origem; atrás do proxy confiável, o IP real do cliente."""
    return request.client.host if request.client else "desconhecido"


def _user_agent(request: Request) -> str | None:
    valor = request.headers.get("user-agent")
    return None if valor is None else valor[:_TAMANHO_MAXIMO_USER_AGENT]


@router.post(
    "/login",
    response_model=SessaoSaida,
    responses=respostas_de_erro(
        CodigoErro.CREDENCIAIS_INVALIDAS,
        CodigoErro.LIMITE_TENTATIVAS,
        CodigoErro.CSRF_INVALIDO,
        CodigoErro.VALIDACAO_FALHOU,
    ),
)
def login(
    corpo: LoginEntrada,
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    senhas: Annotated[ServicoDeSenhas, Depends(get_servico_de_senhas)],
    agora: Annotated[datetime, Depends(get_relogio)],
) -> SessaoSaida:
    """Autentica com e-mail e senha e abre uma sessão (cookie `HttpOnly`).

    Qualquer falha de credencial, conta inativa ou conta bloqueada produz a
    mesma resposta, para não revelar quais contas existem.
    """
    servico = ServicoDeAutenticacao(session, settings, senhas)
    try:
        resultado = servico.entrar(
            corpo.email,
            corpo.senha,
            ip=_ip(request),
            user_agent=_user_agent(request),
            agora=agora,
        )
    except LimiteDeTentativas as limite:
        session.commit()
        raise ErroDeApi(
            CodigoErro.LIMITE_TENTATIVAS,
            "Muitas tentativas. Aguarde alguns minutos e tente novamente.",
            headers={"Retry-After": str(limite.retry_after)},
        ) from None
    except CredenciaisInvalidas:
        session.commit()  # preserva o registro da tentativa (base do bloqueio)
        raise ErroDeApi(
            CodigoErro.CREDENCIAIS_INVALIDAS, _MENSAGEM_CREDENCIAIS
        ) from None

    session.commit()
    definir_cookie(response, settings, resultado.token)
    return SessaoSaida(
        usuario=UsuarioSaida(
            id=resultado.usuario.id,
            email=resultado.usuario.email,
            nome=resultado.usuario.nome,
            papel=resultado.usuario.papel,
            troca_senha_pendente=resultado.usuario.troca_senha_pendente,
        ),
        csrf_token=resultado.sessao.csrf_token,
    )


@router.get(
    "/me",
    response_model=SessaoSaida,
    responses=respostas_de_erro(CodigoErro.NAO_AUTENTICADO),
)
def sessao_atual(
    autenticada: Annotated[SessaoAutenticada, Depends(get_sessao_autenticada)],
) -> SessaoSaida:
    """Devolve o usuário da sessão e o token CSRF, usado ao abrir o aplicativo."""
    return SessaoSaida(
        usuario=UsuarioSaida(
            id=autenticada.usuario_id,
            email=autenticada.email,
            nome=autenticada.nome,
            papel=autenticada.papel,
            troca_senha_pendente=autenticada.troca_senha_pendente,
        ),
        csrf_token=autenticada.csrf_token,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=respostas_de_erro(CodigoErro.NAO_AUTENTICADO, CodigoErro.CSRF_INVALIDO),
)
def logout(
    autenticada: Annotated[SessaoAutenticada, Depends(get_sessao_autenticada)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    agora: Annotated[datetime, Depends(get_relogio)],
) -> Response:
    """Revoga a sessão no servidor e descarta o cookie."""
    sessao = SessaoRepository(session).get_by_id(autenticada.sessao_id)
    if sessao is not None:
        ServicoDeSessoes(session, settings).revogar(sessao, agora=agora)
        registrar_evento(
            "logout", usuario_id=autenticada.usuario_id, sessao_id=autenticada.sessao_id
        )
    session.commit()
    resposta = Response(status_code=status.HTTP_204_NO_CONTENT)
    apagar_cookie(resposta, settings)
    return resposta


@router.post(
    "/senha",
    response_model=TrocaSenhaSaida,
    responses=respostas_de_erro(
        CodigoErro.NAO_AUTENTICADO,
        CodigoErro.CSRF_INVALIDO,
        CodigoErro.CREDENCIAIS_INVALIDAS,
        CodigoErro.SENHA_FRACA,
        CodigoErro.VALIDACAO_FALHOU,
    ),
)
def trocar_senha(
    corpo: TrocaSenhaEntrada,
    request: Request,
    response: Response,
    autenticada: Annotated[SessaoAutenticada, Depends(get_sessao_autenticada)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    senhas: Annotated[ServicoDeSenhas, Depends(get_servico_de_senhas)],
    agora: Annotated[datetime, Depends(get_relogio)],
) -> TrocaSenhaSaida:
    """Troca a senha, encerra todas as sessões e abre uma nova para quem pediu."""
    usuario = UsuarioRepository(session).get_by_id(autenticada.usuario_id)
    if usuario is None:  # conta removida entre o middleware e a rota
        raise ErroDeApi(CodigoErro.NAO_AUTENTICADO, "Autenticação necessária.")

    servico = ServicoDeAutenticacao(session, settings, senhas)
    try:
        resultado = servico.trocar_senha(
            usuario,
            senha_atual=corpo.senha_atual,
            senha_nova=corpo.senha_nova,
            ip=_ip(request),
            user_agent=_user_agent(request),
            agora=agora,
        )
    except CredenciaisInvalidas:
        session.rollback()
        raise ErroDeApi(
            CodigoErro.CREDENCIAIS_INVALIDAS, "A senha atual está incorreta."
        ) from None
    except SenhaFraca as fraca:
        session.rollback()
        # Só o motivo estável vai na resposta; a senha enviada nunca volta.
        raise ErroDeApi(
            CodigoErro.SENHA_FRACA,
            "A nova senha não atende à política de senhas.",
            {"motivo": fraca.motivo},
        ) from None

    session.commit()
    definir_cookie(response, settings, resultado.token)
    return TrocaSenhaSaida(csrf_token=resultado.sessao.csrf_token)
