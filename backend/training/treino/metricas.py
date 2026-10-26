"""Métricas de segmentação e de negócio (avaliacao_spec.md, seção 3).

Dice e IoU medem a sobreposição pixel a pixel; o erro percentual absoluto mede
o que o produto informa. Os erros de segmentação podem se cancelar no
percentual, por isso as duas famílias são reportadas.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

import torch
from torchmetrics.classification import MulticlassConfusionMatrix

from training.treino.configuracao import (
    CLASSES,
    INDICE_PLACA_COBERTA,
    INDICE_PLACA_LIMPA,
    LIMIAR_ATENCAO,
    LIMIAR_TROCAR,
)

AREA_PLACA_MINIMA = 0.05
STATUS = ("ok", "atencao", "trocar")
FAIXAS_IDADE = ((0.0, 30.0, "0-30"), (30.0, 60.0, "30-60"), (60.0, math.inf, "60+"))


def derivar_status(percentual: float) -> str:
    """Status pelo percentual coberto (modelo_spec.md, seção 5.2)."""
    if percentual < LIMIAR_ATENCAO:
        return "ok"
    if percentual <= LIMIAR_TROCAR:
        return "atencao"
    return "trocar"


def _faixa_idade(idade: float) -> str:
    for inicio, fim, rotulo in FAIXAS_IDADE:
        if inicio <= idade < fim:
            return rotulo
    return FAIXAS_IDADE[-1][2]


class AcumuladorMetricas:
    """Acumula predições de um conjunto e calcula as métricas ao final."""

    def __init__(self) -> None:
        self._confusao = MulticlassConfusionMatrix(
            num_classes=len(CLASSES), ignore_index=255
        )
        self._imagens: list[dict[str, Any]] = []

    def atualizar(
        self,
        logits: torch.Tensor,
        alvo: torch.Tensor,
        idades: list[float],
        cores: list[str],
    ) -> None:
        """Soma um lote: `logits` `(B, 3, H, W)`, `alvo` `(B, H, W)`."""
        previsto = logits.argmax(dim=1)
        self._confusao.update(previsto.cpu(), alvo.cpu())
        for i in range(previsto.shape[0]):
            validos = alvo[i] != 255
            pixels = int(validos.sum())
            if pixels == 0:
                continue
            prev_limpa = int(((previsto[i] == INDICE_PLACA_LIMPA) & validos).sum())
            prev_coberta = int(((previsto[i] == INDICE_PLACA_COBERTA) & validos).sum())
            real_limpa = int((alvo[i] == INDICE_PLACA_LIMPA).sum())
            real_coberta = int((alvo[i] == INDICE_PLACA_COBERTA).sum())
            area_prevista = prev_limpa + prev_coberta
            area_real = max(real_limpa + real_coberta, 1)
            self._imagens.append(
                {
                    "previsto": (
                        0.0
                        if area_prevista == 0
                        else prev_coberta / area_prevista * 100.0
                    ),
                    "real": real_coberta / area_real * 100.0,
                    "falha": area_prevista < AREA_PLACA_MINIMA * pixels,
                    "idade": float(idades[i]),
                    "cor": cores[i],
                }
            )

    def resultado(self) -> dict[str, Any]:
        """Métricas do conjunto acumulado."""
        if not self._imagens:
            raise ValueError("Nenhuma amostra acumulada.")
        matriz = self._confusao.compute().double()
        dice, iou = {}, {}
        for indice, classe in enumerate(CLASSES):
            tp = float(matriz[indice, indice])
            fp = float(matriz[:, indice].sum()) - tp
            fn = float(matriz[indice, :].sum()) - tp
            dice[classe] = 1.0 if tp + fp + fn == 0 else 2 * tp / (2 * tp + fp + fn)
            iou[classe] = 1.0 if tp + fp + fn == 0 else tp / (tp + fp + fn)

        erros = [abs(i["previsto"] - i["real"]) for i in self._imagens]
        status_real = [derivar_status(i["real"]) for i in self._imagens]
        status_previsto = [derivar_status(i["previsto"]) for i in self._imagens]
        confusao_status = [[0] * 3 for _ in STATUS]
        for real, previsto in zip(status_real, status_previsto):
            confusao_status[STATUS.index(real)][STATUS.index(previsto)] += 1
        acertos = sum(r == p for r, p in zip(status_real, status_previsto))

        por_idade: dict[str, list[float]] = defaultdict(list)
        por_cor: dict[str, list[float]] = defaultdict(list)
        for imagem, erro in zip(self._imagens, erros):
            por_idade[_faixa_idade(imagem["idade"])].append(erro)
            por_cor[imagem["cor"]].append(erro)

        return {
            "amostras": len(self._imagens),
            "dice_por_classe": dice,
            "iou_por_classe": iou,
            "dice_medio": sum(dice.values()) / len(dice),
            "iou_medio": sum(iou.values()) / len(iou),
            "dice_coberta": dice["placa_coberta"],
            "erro_percentual_medio_pp": sum(erros) / len(erros),
            "erro_percentual_maximo_pp": max(erros),
            "acuracia_status": acertos / len(erros),
            "matriz_status": confusao_status,
            "trocar_como_ok": confusao_status[STATUS.index("trocar")][
                STATUS.index("ok")
            ],
            "falhas_deteccao_placa": sum(1 for i in self._imagens if i["falha"]),
            "erro_por_idade_pp": {
                k: sum(v) / len(v) for k, v in sorted(por_idade.items())
            },
            "erro_por_cor_pp": {k: sum(v) / len(v) for k, v in sorted(por_cor.items())},
        }
