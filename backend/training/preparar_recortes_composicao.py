"""Mantém na biblioteca apenas recortes de placas do conjunto de composição."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from training.dataset_sintetico import _dividir_placas_reais
from training.segmentar_coco_originais import conservar_recortes_de_composicao


def executar(
    placas_reais: Path,
    biblioteca: Path,
    semente: int,
    proporcao_avaliacao: float,
) -> dict:
    """Separa placas por ID e remove recortes exclusivamente de avaliação."""
    composicao, avaliacao = _dividir_placas_reais(
        placas_reais, semente, proporcao_avaliacao
    )
    return conservar_recortes_de_composicao(
        biblioteca,
        {placa.stem for placa in composicao},
        {placa.stem for placa in avaliacao},
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--placas-reais", type=Path, required=True)
    parser.add_argument("--biblioteca", type=Path, required=True)
    parser.add_argument("--semente", type=int, required=True)
    parser.add_argument("--proporcao-avaliacao", type=float, default=0.2)
    argumentos = parser.parse_args()
    resumo = executar(
        argumentos.placas_reais,
        argumentos.biblioteca,
        argumentos.semente,
        argumentos.proporcao_avaliacao,
    )
    print(json.dumps(resumo, ensure_ascii=False, sort_keys=True))
