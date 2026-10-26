"""Contador em memória para limitar operações por chave em uma janela deslizante."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable
from threading import Lock


class LimitadorPorJanela:
    """Conta operações por chave em memória durante uma janela deslizante."""

    def __init__(
        self,
        limite: int,
        janela_segundos: int,
        *,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        """Define o teto, a janela e a fonte de tempo.

        Args:
            limite: operações permitidas dentro da janela.
            janela_segundos: duração da janela deslizante em segundos.
            relogio: função que devolve segundos monotônicos.
        """
        self._limite = limite
        self._janela_segundos = janela_segundos
        self._relogio = relogio
        self._registros: defaultdict[str, deque[float]] = defaultdict(deque)
        self._trava = Lock()

    def tentar(self, chave: str) -> int | None:
        """Registra uma operação se a chave ainda possuir cota.

        Args:
            chave: identificador do titular da cota.

        Returns:
            None quando a operação é permitida; caso contrário, os segundos até
            haver cota novamente.
        """
        agora = self._relogio()
        with self._trava:
            instantes = self._registros[chave]
            while instantes and agora - instantes[0] >= self._janela_segundos:
                instantes.popleft()
            if len(instantes) >= self._limite:
                restante = self._janela_segundos - (agora - instantes[0])
                return max(1, int(restante) + 1)
            instantes.append(agora)
            return None
