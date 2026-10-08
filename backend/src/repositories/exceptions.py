"""Exceções de domínio produzidas pela camada de repositórios."""


class ErroDeDominio(Exception):
    """Base para falhas de persistência expressas em termos do domínio."""


class IdentificadorDuplicado(ErroDeDominio):
    """Indica que outra armadilha já usa o identificador informado."""


class RefilAtivoExistente(ErroDeDominio):
    """Indica que a armadilha já possui um refil sem data de troca."""


class RefilJaEncerrado(ErroDeDominio):
    """Indica que o ciclo já tem uma data de troca registrada."""


class DataTrocaInvalida(ErroDeDominio):
    """Indica que a data de troca antecede a instalação do refil."""
