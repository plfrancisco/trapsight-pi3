"""Listagem e criação de contas acessíveis somente ao gerente."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from src.api.dependencias import get_servico_de_senhas, get_session
from src.api.erros import CodigoErro, ErroDeApi, respostas_de_erro
from src.api.protecao import SessaoAutenticada
from src.api.rotas.auth import get_sessao_autenticada
from src.api.schemas.usuarios import ContaSaida, UsuarioEntrada
from src.entities import Usuario
from src.repositories import EmailDuplicado, UsuarioRepository
from src.services.senhas import SenhaFraca, ServicoDeSenhas
from src.services.usuarios import AcessoNegado, ServicoDeUsuarios, exigir_gerente

router = APIRouter(
    prefix="/usuarios",
    tags=["Contas"],
    responses=respostas_de_erro(CodigoErro.NAO_AUTENTICADO, CodigoErro.ACESSO_NEGADO),
)


def get_gerente(
    autenticada: Annotated[SessaoAutenticada, Depends(get_sessao_autenticada)],
    session: Annotated[Session, Depends(get_session)],
    response: Response,
) -> Usuario:
    """Consulta o papel atual no banco, sem confiar na sessão ou no cliente."""
    usuario = UsuarioRepository(session).get_by_id(autenticada.usuario_id)
    if usuario is None:
        raise ErroDeApi(CodigoErro.NAO_AUTENTICADO, "Autenticação necessária.")
    try:
        exigir_gerente(usuario)
    except AcessoNegado:
        raise ErroDeApi(
            CodigoErro.ACESSO_NEGADO, "Acesso restrito ao gerente."
        ) from None
    response.headers["Cache-Control"] = "no-store"
    return usuario


@router.get("", response_model=list[ContaSaida])
def listar_usuarios(
    gerente: Annotated[Usuario, Depends(get_gerente)],
    session: Annotated[Session, Depends(get_session)],
) -> list[ContaSaida]:
    """Lista as projeções públicas das contas em ordem de e-mail."""
    return [
        ContaSaida.model_validate(usuario)
        for usuario in UsuarioRepository(session).list_all()
    ]


@router.post(
    "",
    status_code=201,
    response_model=ContaSaida,
    responses=respostas_de_erro(
        CodigoErro.CSRF_INVALIDO,
        CodigoErro.EMAIL_JA_CADASTRADO,
        CodigoErro.SENHA_FRACA,
        CodigoErro.VALIDACAO_FALHOU,
    ),
)
def criar_usuario(
    corpo: UsuarioEntrada,
    gerente: Annotated[Usuario, Depends(get_gerente)],
    session: Annotated[Session, Depends(get_session)],
    senhas: Annotated[ServicoDeSenhas, Depends(get_servico_de_senhas)],
) -> ContaSaida:
    """Cria somente operador e confirma a transação após todas as validações."""
    try:
        usuario = ServicoDeUsuarios(session, senhas).criar_operador(
            gerente, email=corpo.email, nome=corpo.nome, senha=corpo.senha
        )
    except EmailDuplicado:
        session.rollback()
        raise ErroDeApi(
            CodigoErro.EMAIL_JA_CADASTRADO, "Já existe uma conta com este e-mail."
        ) from None
    except SenhaFraca as fraca:
        session.rollback()
        raise ErroDeApi(
            CodigoErro.SENHA_FRACA,
            "A senha inicial não atende à política de senhas.",
            {"motivo": fraca.motivo},
        ) from None
    session.commit()
    return ContaSaida.model_validate(usuario)
