"""Função de perda do treino (treino_spec.md, seção 3).

Numa placa com 10% de cobertura, `placa_coberta` é minoria absoluta dos pixels:
uma entropia cruzada simples converge para prever `placa_limpa` em toda a placa,
com boa acurácia de pixel e erro percentual alto. A perda combina três termos:

    L = L_ce + L_dice + lambda * L_area
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
import torch.nn.functional as F
from torch import nn

from training.treino.configuracao import INDICE_PLACA_COBERTA, INDICE_PLACA_LIMPA

EPSILON = 1e-6


@dataclass(frozen=True)
class ResultadoPerda:
    """Perda total e seus componentes, para registro por época."""

    total: torch.Tensor
    ce: torch.Tensor
    dice: torch.Tensor
    area: torch.Tensor


def percentual_suave(probabilidades: torch.Tensor) -> torch.Tensor:
    """Fração coberta por imagem, calculada sobre probabilidades suaves.

    O denominador é a área de placa prevista, como em modelo_spec.md, seção 5.
    Entrada `(B, 3, H, W)`; saída `(B,)` com valores entre 0 e 1.
    """
    limpa = probabilidades[:, INDICE_PLACA_LIMPA].sum(dim=(1, 2))
    coberta = probabilidades[:, INDICE_PLACA_COBERTA].sum(dim=(1, 2))
    return coberta / (limpa + coberta).clamp_min(EPSILON)


def percentual_do_gabarito(alvo: torch.Tensor) -> torch.Tensor:
    """Fração coberta por imagem no gabarito `(B, H, W)`; 0 sem pixel de placa."""
    limpa = (alvo == INDICE_PLACA_LIMPA).sum(dim=(1, 2)).float()
    coberta = (alvo == INDICE_PLACA_COBERTA).sum(dim=(1, 2)).float()
    return coberta / (limpa + coberta).clamp_min(1.0)


class PerdaSegmentacao(nn.Module):
    """Entropia cruzada ponderada, Dice ponderado e termo de área opcional."""

    def __init__(self, pesos_classe: torch.Tensor, lambda_area: float = 0.0) -> None:
        super().__init__()
        pesos = pesos_classe.detach().clone().float()
        self.register_buffer("pesos_ce", pesos)
        # `placa_coberta` recebe ao menos o maior peso entre as classes.
        pesos_dice = pesos.clone()
        pesos_dice[INDICE_PLACA_COBERTA] = pesos.max()
        self.register_buffer("pesos_dice", pesos_dice)
        self.lambda_area = float(lambda_area)

    def forward(self, logits: torch.Tensor, alvo: torch.Tensor) -> ResultadoPerda:
        logits = logits.float()
        ce = F.cross_entropy(logits, alvo, weight=self.pesos_ce)

        probabilidades = logits.softmax(dim=1)
        um_quente = F.one_hot(alvo, num_classes=probabilidades.shape[1])
        um_quente = um_quente.permute(0, 3, 1, 2).float()
        intersecao = (probabilidades * um_quente).sum(dim=(0, 2, 3))
        soma = probabilidades.sum(dim=(0, 2, 3)) + um_quente.sum(dim=(0, 2, 3))
        dice_por_classe = (2.0 * intersecao + EPSILON) / (soma + EPSILON)
        dice = ((1.0 - dice_por_classe) * self.pesos_dice).sum() / self.pesos_dice.sum()

        if self.lambda_area > 0.0:
            area = (
                (percentual_suave(probabilidades) - percentual_do_gabarito(alvo))
                .abs()
                .mean()
            )
        else:
            area = torch.zeros((), device=logits.device)

        total = ce + dice + self.lambda_area * area
        return ResultadoPerda(
            total=total, ce=ce.detach(), dice=dice.detach(), area=area.detach()
        )
