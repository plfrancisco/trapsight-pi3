"""Apoio dos testes de API: contas, sessões e clientes já autenticados."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.api.sessao_http import nome_do_cookie
from src.entities import Usuario
from src.entities.papel import PapelUsuario
from src.repositories import UsuarioRepository
from src.services.sessoes import ServicoDeSessoes

ORIGEM_DE_TESTE = "http://localhost:5173"
EMAIL_DE_TESTE = "operador@exemplo.com"
# Frase longa e sem relação com o e-mail nem com o produto: passa na política.
SENHA_DE_TESTE = "uma frase longa e bem diferente 2026"


@dataclass(frozen=True)
class CredenciaisDeTeste:
    """Token de sessão e token CSRF de uma sessão criada para os testes."""

    token: str
    csrf_token: str
    usuario: Usuario


def criar_usuario(
    session: Session,
    app,
    *,
    email: str = EMAIL_DE_TESTE,
    nome: str = "Operador de Teste",
    senha: str = SENHA_DE_TESTE,
    papel: PapelUsuario = PapelUsuario.OPERADOR,
) -> Usuario:
    """Cria uma conta com o hash real (Argon2id) usado pela aplicação.

    Args:
        session: sessão do teste.
        app: aplicação, que guarda o serviço de senhas.
        email: e-mail da conta, já normalizado.
        nome: nome de exibição.
        senha: senha em claro da conta.
        papel: papel da conta criada para o cenário.

    Returns:
        O usuário persistido na transação do teste.
    """
    hash_da_senha = app.state.servico_de_senhas.gerar_hash(senha)
    return UsuarioRepository(session).create(
        email=email, nome=nome, senha_hash=hash_da_senha, papel=papel
    )


def criar_sessao(
    session: Session, app, usuario: Usuario, *, ip: str = "127.0.0.1"
) -> CredenciaisDeTeste:
    """Abre uma sessão para o usuário pelo serviço real, sem passar pelo login.

    Args:
        session: sessão do teste.
        app: aplicação, que guarda configuração e relógio.
        usuario: dono da sessão.
        ip: endereço de origem registrado.

    Returns:
        O token em claro e o token CSRF da sessão.
    """
    sessao, token = ServicoDeSessoes(session, app.state.settings).criar(
        usuario, agora=app.state.relogio(), ip=ip, user_agent="pytest"
    )
    return CredenciaisDeTeste(
        token=token, csrf_token=sessao.csrf_token, usuario=usuario
    )


def aplicar_credenciais(client: TestClient, credenciais: CredenciaisDeTeste) -> None:
    """Configura o cliente como um navegador já logado.

    Args:
        client: cliente de teste da aplicação.
        credenciais: sessão a usar.
    """
    app = client.app
    client.cookies.clear()
    client.cookies.set(nome_do_cookie(app.state.settings), credenciais.token)
    client.headers["X-CSRF-Token"] = credenciais.csrf_token
    client.headers["Origin"] = ORIGEM_DE_TESTE


def autenticar_cliente(
    client: TestClient,
    session: Session,
    *,
    provedor: Callable[[], AbstractContextManager[Session]] | None = None,
    email: str = EMAIL_DE_TESTE,
) -> CredenciaisDeTeste:
    """Cria usuário e sessão e deixa o cliente autenticado.

    O middleware de proteção abre a própria sessão de banco; aqui ele passa a
    usar a sessão transacional do teste, para enxergar os dados ainda não
    confirmados.

    Args:
        client: cliente de teste da aplicação.
        session: sessão transacional do teste.
        provedor: substitui o provedor de sessões do middleware (padrão: a sessão
            do teste, sem fechá-la).
        email: e-mail da conta criada.

    Returns:
        As credenciais da sessão criada.
    """
    app = client.app
    app.state.provedor_de_sessao = provedor or (lambda: nullcontext(session))
    usuario = criar_usuario(session, app, email=email)
    credenciais = criar_sessao(session, app, usuario)
    aplicar_credenciais(client, credenciais)
    return credenciais
