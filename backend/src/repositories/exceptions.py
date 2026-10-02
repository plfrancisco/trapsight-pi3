"""Exceções de domínio produzidas pela camada de repositórios."""


class IdentificadorDuplicado(Exception):
    """Indica que outra armadilha já usa o identificador informado."""
