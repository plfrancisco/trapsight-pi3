"""Exceções de domínio produzidas pela camada de repositórios."""


class IdentificadorDuplicado(Exception):
    """Indica que outra armadilha já usa o identificador informado."""


class RefilAtivoExistente(Exception):
    """Indica que a armadilha já possui um refil sem data de troca."""
