"""Fixtures do treino: dataset minúsculo e configuração rápida para CPU.

Estes testes exigem o grupo de dependências `treino` (PyTorch, Albumentations,
segmentation_models_pytorch, torchmetrics); sem ele, a coleta os ignora.
"""

from __future__ import annotations

import importlib.util
import json
from collections.abc import Callable
from pathlib import Path

import pytest
from PIL import Image

from training.treino.configuracao import Configuracao

_DEPENDENCIAS = (
    "torch",
    "albumentations",
    "segmentation_models_pytorch",
    "torchmetrics",
    "numpy",
)
if any(importlib.util.find_spec(nome) is None for nome in _DEPENDENCIAS):
    collect_ignore_glob = ["test_*.py"]

TAMANHO = 64
CAIXA = (8, 56)  # a placa ocupa linhas e colunas 8..55
AREA_PLACA = (CAIXA[1] - CAIXA[0]) ** 2
FAIXAS_ALVO = {"ok": 20.0, "atencao": 55.0, "trocar": 85.0}


def _escrever_amostra(raiz: Path, identificador: str, percentual_alvo: float) -> float:
    """Grava imagem e máscara e devolve o percentual exato da máscara."""
    import numpy as np

    mascara = np.zeros((TAMANHO, TAMANHO), dtype=np.uint8)
    mascara[CAIXA[0] : CAIXA[1], CAIXA[0] : CAIXA[1]] = 1
    coberto = round(percentual_alvo / 100.0 * AREA_PLACA)
    posicoes = np.flatnonzero(mascara.ravel() == 1)[:coberto]
    mascara.ravel()[posicoes] = 2

    imagem = np.full((TAMANHO, TAMANHO, 3), 90, dtype=np.uint8)
    imagem[mascara == 1] = 220
    imagem[mascara == 2] = 40
    (raiz / "imagens").mkdir(exist_ok=True)
    (raiz / "mascaras").mkdir(exist_ok=True)
    Image.fromarray(imagem).save(raiz / "imagens" / f"{identificador}.png")
    Image.fromarray(mascara).save(raiz / "mascaras" / f"{identificador}.png")
    return float(coberto) / AREA_PLACA * 100.0


@pytest.fixture
def criar_dataset(tmp_path: Path) -> Callable[..., Path]:
    """Gera um dataset de 6 amostras por conjunto (2 por faixa de cobertura)."""

    def criar(
        idade: Callable[[float], float] = lambda _cobertura: 30.0,
        faixa_do_treino: str | None = None,
        semente_compartilhada: bool = False,
    ) -> Path:
        raiz = tmp_path / "dataset"
        raiz.mkdir(exist_ok=True)
        (raiz / "configuracao.json").write_text(json.dumps({"semente_global": 7}))
        linhas = []
        semente = 1000
        for conjunto in ("treino", "validacao", "teste"):
            for numero in range(6):
                faixa = list(FAIXAS_ALVO)[numero % 3]
                if conjunto == "treino" and faixa_do_treino:
                    faixa = faixa_do_treino
                identificador = f"{conjunto}_{numero:03d}"
                variacao = float(numero // 3) * 3.0
                percentual = _escrever_amostra(
                    raiz, identificador, FAIXAS_ALVO[faixa] + variacao
                )
                semente += 1
                linhas.append(
                    {
                        "id": identificador,
                        "semente": 1001
                        if semente_compartilhada and numero == 0
                        else semente,
                        "conjunto": conjunto,
                        "faixa_cobertura_alvo": faixa,
                        "percentual_cobertura_real": percentual,
                        "idade_simulada_dias": idade(percentual),
                        "dominante_cor": "branco_corrigido"
                        if numero % 2
                        else "violeta_azulada",
                    }
                )
        (raiz / "metadados.jsonl").write_text(
            "\n".join(json.dumps(linha) for linha in linhas) + "\n", encoding="utf-8"
        )
        return raiz

    return criar


@pytest.fixture
def configuracao_rapida(
    tmp_path: Path, criar_dataset: Callable[..., Path]
) -> Configuracao:
    """Configuração mínima para treinar em CPU em poucos segundos."""
    return Configuracao(
        nome="teste",
        dataset=str(criar_dataset()),
        saida=str(tmp_path / "execucoes"),
        largura=TAMANHO,
        altura=TAMANHO,
        encoder_pretreinado=False,
        congelar_encoder_epocas=1,
        batch_por_passo=2,
        batch_efetivo=4,
        epocas_maximas=2,
        aquecimento_epocas=1,
        paciencia=5,
        precisao_mista=False,
        num_workers=0,
    )
