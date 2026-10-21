"""Limite de análises por usuário, em janela deslizante de um minuto."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable
from threading import Lock

_JANELA_SEGUNDOS = 60


class LimitadorDeAnalises:
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
        self._limite = limite_por_minuto
        self._relogio = relogio
        self._registros: defaultdict[str, deque[float]] = defaultdict(deque)
        self._trava = Lock()

    def tentar(self, chave: str) -> int | None:
        """Registra uma análise se ainda houver cota.

        Args:
            chave: identificador do usuário.

        Returns:
            None quando a análise é permitida; caso contrário, os segundos até
            haver cota de novo.
        """
        agora = self._relogio()
        with self._trava:
            instantes = self._registros[chave]
            while instantes and agora - instantes[0] >= _JANELA_SEGUNDOS:
                instantes.popleft()
            if len(instantes) >= self._limite:
                return max(1, int(_JANELA_SEGUNDOS - (agora - instantes[0])) + 1)
            instantes.append(agora)
            return None
