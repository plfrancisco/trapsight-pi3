"""Seleção do melhor ponto e parada antecipada (treino_spec.md, seções 4.2 e 4.3).

A decisão usa apenas a validação. Ordem do critério:

1. menor número de casos `trocar` classificados como `ok` (erro crítico);
2. menor erro percentual absoluto médio;
3. maior Dice de `placa_coberta`, como desempate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def chave_de_selecao(metricas: dict[str, Any]) -> tuple[int, float, float]:
    """Chave ordenável; valores menores são melhores."""
    return (
        int(metricas["trocar_como_ok"]),
        float(metricas["erro_percentual_medio_pp"]),
        -float(metricas["dice_coberta"]),
    )


@dataclass(frozen=True)
class DecisaoEpoca:
    """O que a seleção decide ao fim de uma época."""

    melhor_ponto: bool
    melhor_por_dice: bool
    parar: bool
    epocas_sem_melhora: int


class SelecaoMelhorPonto:
    """Guarda o melhor ponto e a paciência da parada antecipada."""

    def __init__(self, paciencia: int, melhora_minima_pp: float) -> None:
        self.paciencia = paciencia
        self.melhora_minima_pp = melhora_minima_pp
        self._melhor: tuple[int, float, float] | None = None
        self._melhor_dice: float | None = None
        self._referencia: tuple[int, float] | None = None
        self.epocas_sem_melhora = 0

    def atualizar(self, metricas: dict[str, Any]) -> DecisaoEpoca:
        """Registra uma época de validação e decide checkpoint e parada."""
        chave = chave_de_selecao(metricas)
        melhor_ponto = self._melhor is None or chave < self._melhor
        if melhor_ponto:
            self._melhor = chave

        dice = float(metricas["dice_coberta"])
        melhor_por_dice = self._melhor_dice is None or dice > self._melhor_dice
        if melhor_por_dice:
            self._melhor_dice = dice

        critico, erro = chave[0], chave[1]
        if self._referencia is None:
            melhora_relevante = True
        else:
            ref_critico, ref_erro = self._referencia
            melhora_relevante = critico < ref_critico or (
                critico == ref_critico and erro <= ref_erro - self.melhora_minima_pp
            )
        if melhora_relevante:
            self._referencia = (critico, erro)
            self.epocas_sem_melhora = 0
        else:
            self.epocas_sem_melhora += 1

        return DecisaoEpoca(
            melhor_ponto=melhor_ponto,
            melhor_por_dice=melhor_por_dice,
            parar=self.epocas_sem_melhora >= self.paciencia,
            epocas_sem_melhora=self.epocas_sem_melhora,
        )
