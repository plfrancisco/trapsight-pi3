"""Papéis de acesso persistidos para as contas do sistema."""

from enum import StrEnum


class PapelUsuario(StrEnum):
    """Valores aceitos pelo banco para autorização de usuários."""

    GERENTE = "gerente"
    OPERADOR = "operador"
