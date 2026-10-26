"""Limite de criação de contas por gerente."""

import time
from collections.abc import Callable

from src.services.limitador import LimitadorPorJanela


class LimitadorDeContas(LimitadorPorJanela):
    """Conta criações de conta por gerente durante uma hora."""

    def __init__(
        self,
        limite_por_hora: int,
        *,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        """Define a quantidade máxima de contas criadas por hora.

        Args:
            limite_por_hora: contas permitidas por gerente em 60 minutos.
            relogio: função que devolve segundos monotônicos.
        """
        super().__init__(limite_por_hora, janela_segundos=3600, relogio=relogio)
