"""Estados persistidos para classificar o resultado de uma análise."""

from enum import StrEnum


class StatusAnalise(StrEnum):
    """Valores textuais aceitos pela coluna de status da análise."""

    OK = "ok"
    ATENCAO = "atencao"
    TROCAR = "trocar"
