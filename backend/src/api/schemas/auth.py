"""Contratos de entrada e saída dos endpoints de autenticação."""

from uuid import UUID

from pydantic import BaseModel, Field

from src.api.schemas.entrada import EntradaBase
from src.entities.papel import PapelUsuario


class LoginEntrada(EntradaBase):
    """Credenciais enviadas ao login; campos desconhecidos são recusados."""

    email: str = Field(min_length=3, max_length=254)
    senha: str = Field(min_length=1, max_length=128)


class TrocaSenhaEntrada(EntradaBase):
    """Troca da própria senha; a política é aplicada pelo serviço (SENHA_FRACA)."""

    senha_atual: str = Field(min_length=1, max_length=128)
    # O teto folgado deixa a política responder SENHA_FRACA (e não VALIDACAO_FALHOU)
    # para senhas acima de 128 caracteres; o Argon2 só roda depois da política.
    senha_nova: str = Field(min_length=1, max_length=1024)


class UsuarioSaida(BaseModel):
    """Dados do usuário que podem ir ao navegador (nunca o hash)."""

    id: UUID
    email: str
    nome: str
    papel: PapelUsuario


class SessaoSaida(BaseModel):
    """Usuário autenticado e o token CSRF da sessão."""

    usuario: UsuarioSaida
    csrf_token: str


class TrocaSenhaSaida(BaseModel):
    """Token CSRF da sessão renovada depois da troca de senha."""

    csrf_token: str
