"""Limite de análises por usuário, em janela deslizante de um minuto."""

from __future__ import annotations

import time
from collections.abc import Callable

from src.services.limitador import LimitadorPorJanela


class LimitadorDeAnalises(LimitadorPorJanela):
    """Conta análises por usuário em memória.

    Adequado a um único processo (o contêiner do backend roda um só). Se o
    backend passar a ter vários processos, o contador precisa ir para o banco.
    """

    def __init__(
        self,
        limite_por_minuto: int,
        *,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        """Define o teto e a fonte de tempo (substituível em testes).

        Args:
            limite_por_minuto: análises permitidas por usuário em 60 segundos.
            relogio: função que devolve segundos monotônicos.
        """
        super().__init__(limite_por_minuto, janela_segundos=60, relogio=relogio)
