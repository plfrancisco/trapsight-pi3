"""Gestão de contas pela linha de comando.

Não existe cadastro público; papéis privilegiados são concedidos aqui.
Uso: `python -m src.cli <comando> --help`.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.config.database import create_database_engine, create_session_factory
from src.config.settings import Settings
from src.entities import Usuario
from src.entities.papel import PapelUsuario
from src.repositories import EmailDuplicado, UsuarioRepository
from src.repositories.exceptions import GerenteJaExiste
from src.services.auditoria import configurar_auditoria, registrar_evento
from src.services.autenticacao import normalizar_email
from src.services.senhas import SenhaFraca, ServicoDeSenhas, validar_politica
from src.services.sessoes import ServicoDeSessoes

_MOTIVOS = {
    "curta": "a senha precisa ter ao menos 15 caracteres",
    "longa": "a senha pode ter no máximo 128 caracteres",
    "comum": "a senha é comum demais",
    "trivial": "a senha é uma sequência ou repetição simples",
    "contextual": "a senha não pode derivar do e-mail, do nome ou do produto",
    "igual_atual": "a senha nova precisa ser diferente da senha atual",
}


class ErroDeComando(Exception):
    """Falha esperada de um comando; a mensagem é mostrada ao operador."""


def _buscar(repositorio: UsuarioRepository, email: str) -> Usuario:
    usuario = repositorio.get_by_email(normalizar_email(email))
    if usuario is None:
        raise ErroDeComando("Conta não encontrada.")
    return usuario


def criar_usuario(
    session: Session,
    senhas: ServicoDeSenhas,
    *,
    email: str,
    nome: str,
    senha: str,
    papel: PapelUsuario = PapelUsuario.OPERADOR,
) -> Usuario:
    """Cria uma conta ativa depois de validar a política de senhas.

    Args:
        session: sessão cuja transação o chamador confirma.
        senhas: serviço de hash de senhas.
        email: e-mail da conta, como digitado.
        nome: nome de exibição.
        senha: senha inicial em claro.
        papel: papel atribuído pela administração local.

    Returns:
        A conta criada.

    Raises:
        ErroDeComando: se a senha violar a política ou o e-mail já existir.
    """
    email_normalizado = normalizar_email(email)
    if not nome.strip():
        raise ErroDeComando("Informe o nome.")
    try:
        validar_politica(senha, email=email_normalizado, nome=nome)
    except SenhaFraca as fraca:
        raise ErroDeComando(_MOTIVOS[fraca.motivo].capitalize() + ".") from None
    try:
        usuario = UsuarioRepository(session).create(
            email=email_normalizado,
            nome=nome.strip(),
            senha_hash=senhas.gerar_hash(senha),
            papel=papel,
        )
    except EmailDuplicado:
        raise ErroDeComando("Já existe uma conta com este e-mail.") from None
    except GerenteJaExiste:
        raise ErroDeComando(
            "Já existe um gerente. Rebaixe a conta atual antes."
        ) from None
    registrar_evento("conta_criada", usuario_id=usuario.id, criado_por_id=None)
    return usuario


def definir_papel(
    session: Session,
    settings: Settings,
    *,
    email: str,
    papel: PapelUsuario,
    agora: datetime,
) -> Usuario:
    """Define o papel pela administração local e encerra todas as sessões.

    Raises:
        ErroDeComando: Se a conta não existir ou já houver outro gerente.
    """
    usuario = _buscar(UsuarioRepository(session), email)
    try:
        UsuarioRepository(session).definir_papel(usuario, papel)
    except GerenteJaExiste:
        raise ErroDeComando(
            "Já existe um gerente. Rebaixe a conta atual antes."
        ) from None
    ServicoDeSessoes(session, settings).revogar_todas(usuario, agora=agora)
    registrar_evento("papel_alterado", usuario_id=usuario.id, motivo=papel.value)
    return usuario


def redefinir_senha(
    session: Session,
    settings: Settings,
    senhas: ServicoDeSenhas,
    *,
    email: str,
    senha: str,
    agora: datetime,
) -> Usuario:
    """Troca a senha de uma conta, encerra todas as sessões e remove o bloqueio.

    Args:
        session: sessão cuja transação o chamador confirma.
        settings: configuração da aplicação.
        senhas: serviço de hash de senhas.
        email: e-mail da conta.
        senha: nova senha em claro.
        agora: instante da operação.

    Returns:
        A conta atualizada.

    Raises:
        ErroDeComando: se a conta não existir ou a senha violar a política.
    """
    repositorio = UsuarioRepository(session)
    usuario = _buscar(repositorio, email)
    try:
        validar_politica(senha, email=usuario.email, nome=usuario.nome)
    except SenhaFraca as fraca:
        raise ErroDeComando(_MOTIVOS[fraca.motivo].capitalize() + ".") from None
    repositorio.definir_senha_hash(usuario, senhas.gerar_hash(senha), agora=agora)
    repositorio.definir_bloqueio(usuario, None)
    ServicoDeSessoes(session, settings).revogar_todas(usuario, agora=agora)
    registrar_evento("senha_redefinida", usuario_id=usuario.id)
    return usuario


def alterar_ativo(
    session: Session,
    settings: Settings,
    *,
    email: str,
    ativo: bool,
    agora: datetime,
) -> Usuario:
    """Ativa ou desativa uma conta; desativar também encerra as sessões abertas.

    Args:
        session: sessão cuja transação o chamador confirma.
        settings: configuração da aplicação.
        email: e-mail da conta.
        ativo: novo estado.
        agora: instante da operação.

    Returns:
        A conta atualizada.

    Raises:
        ErroDeComando: se a conta não existir.
    """
    repositorio = UsuarioRepository(session)
    usuario = _buscar(repositorio, email)
    repositorio.definir_ativo(usuario, ativo=ativo)
    if not ativo:
        ServicoDeSessoes(session, settings).revogar_todas(usuario, agora=agora)
    registrar_evento(
        "conta_ativada" if ativo else "conta_desativada", usuario_id=usuario.id
    )
    return usuario


def desbloquear(session: Session, *, email: str) -> Usuario:
    """Remove o bloqueio temporário por tentativas de login.

    Args:
        session: sessão cuja transação o chamador confirma.
        email: e-mail da conta.

    Returns:
        A conta atualizada.

    Raises:
        ErroDeComando: se a conta não existir.
    """
    repositorio = UsuarioRepository(session)
    usuario = _buscar(repositorio, email)
    repositorio.definir_bloqueio(usuario, None)
    registrar_evento("conta_desbloqueada", usuario_id=usuario.id)
    return usuario


def listar(session: Session) -> list[str]:
    """Descreve as contas existentes, sem qualquer dado de senha.

    Args:
        session: sessão de leitura.

    Returns:
        Uma linha por conta: e-mail, nome e situação.
    """
    return [
        f"{usuario.email}\t{usuario.nome}\t{'ativa' if usuario.ativo else 'desativada'}"
        for usuario in UsuarioRepository(session).list_all()
    ]


def _ler_senha(da_entrada_padrao: bool) -> str:
    if da_entrada_padrao:
        return sys.stdin.readline().rstrip("\r\n")
    senha = getpass.getpass("Senha: ")
    if senha != getpass.getpass("Repita a senha: "):
        raise ErroDeComando("As senhas não conferem.")
    return senha


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m src.cli", description=__doc__)
    comandos = parser.add_subparsers(dest="comando", required=True)

    criar = comandos.add_parser("criar-usuario", help="cria uma conta")
    criar.add_argument("--email", required=True)
    criar.add_argument("--nome", required=True)
    criar.add_argument(
        "--papel",
        type=PapelUsuario,
        choices=list(PapelUsuario),
        default=PapelUsuario.OPERADOR,
    )
    papel = comandos.add_parser("definir-papel", help="define papel e encerra sessões")
    papel.add_argument("--email", required=True)
    papel.add_argument(
        "--papel", required=True, type=PapelUsuario, choices=list(PapelUsuario)
    )
    redefinir = comandos.add_parser("redefinir-senha", help="define nova senha")
    redefinir.add_argument("--email", required=True)
    for nome in ("criar-usuario", "redefinir-senha"):
        comandos.choices[nome].add_argument(
            "--senha-stdin",
            action="store_true",
            help="lê a senha da entrada padrão em vez de perguntar",
        )
    for nome, ajuda in (
        ("desativar-usuario", "desativa a conta e encerra as sessões"),
        ("ativar-usuario", "reativa a conta"),
        ("desbloquear-usuario", "remove o bloqueio por tentativas"),
    ):
        comandos.add_parser(nome, help=ajuda).add_argument("--email", required=True)
    comandos.add_parser("listar-usuarios", help="lista as contas")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Executa um comando e confirma a transação somente em caso de sucesso.

    Args:
        argv: argumentos; por padrão, os da linha de comando.

    Returns:
        Código de saída do processo.
    """
    args = _parser().parse_args(argv)
    configurar_auditoria()
    settings = Settings()
    senhas = ServicoDeSenhas(
        memoria_kib=settings.argon2_memoria_kib,
        iteracoes=settings.argon2_iteracoes,
        paralelismo=settings.argon2_paralelismo,
    )
    engine = create_database_engine(settings.database_url.get_secret_value())
    agora = datetime.now(timezone.utc)
    try:
        with create_session_factory(engine)() as session:
            try:
                saida = _executar(args, session, settings, senhas, agora)
                session.commit()
            except ErroDeComando as erro:
                session.rollback()
                print(f"Erro: {erro}", file=sys.stderr)
                return 1
    finally:
        engine.dispose()
    for linha in saida:
        print(linha)
    return 0


def _executar(
    args: argparse.Namespace,
    session: Session,
    settings: Settings,
    senhas: ServicoDeSenhas,
    agora: datetime,
) -> list[str]:
    comando = args.comando
    if comando == "criar-usuario":
        usuario = criar_usuario(
            session,
            senhas,
            email=args.email,
            nome=args.nome,
            senha=_ler_senha(args.senha_stdin),
            papel=args.papel,
        )
        return [f"Conta criada: {usuario.email}"]
    if comando == "definir-papel":
        usuario = definir_papel(
            session, settings, email=args.email, papel=args.papel, agora=agora
        )
        return [f"Papel definido e sessões encerradas: {usuario.email}"]
    if comando == "redefinir-senha":
        usuario = redefinir_senha(
            session,
            settings,
            senhas,
            email=args.email,
            senha=_ler_senha(args.senha_stdin),
            agora=agora,
        )
        return [f"Senha redefinida e sessões encerradas: {usuario.email}"]
    if comando in ("desativar-usuario", "ativar-usuario"):
        usuario = alterar_ativo(
            session,
            settings,
            email=args.email,
            ativo=comando == "ativar-usuario",
            agora=agora,
        )
        return [
            f"Conta {'ativada' if usuario.ativo else 'desativada'}: {usuario.email}"
        ]
    if comando == "desbloquear-usuario":
        return [f"Conta desbloqueada: {desbloquear(session, email=args.email).email}"]
    return listar(session)


if __name__ == "__main__":
    raise SystemExit(main())
