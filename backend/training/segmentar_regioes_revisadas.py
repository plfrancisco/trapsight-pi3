"""Propõe silhuetas SAM apenas para regiões já decididas como inseto.

A classe é uma entrada da revisão, nunca uma saída do score SAM. As propostas
continuam pendentes de conferência mesmo quando o score é alto.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from training.estruturas_bases import (
    carregar_estruturas,
    inventariar,
    validar_inventario,
)
from training.teste_real_ums import _carregar_sam


def codificar_rle(mascara: np.ndarray) -> list[list[int]]:
    """Serializa silhuetas sem depender de formatos externos de anotação."""
    linhas = []
    for y, linha in enumerate(mascara):
        bordas = np.diff(np.pad(linha.astype(np.int8), (1, 1)))
        for x0, x1 in zip(
            np.flatnonzero(bordas == 1), np.flatnonzero(bordas == -1), strict=True
        ):
            linhas.append([y, int(x0), int(x1)])
    return linhas


def segmentar(predictor, rgb: np.ndarray, labels: np.ndarray, regiao: dict) -> dict:
    """Usa a candidata como prompt, sem reaproveitá-la como máscara de verdade."""
    if regiao["decisao"] != "inseto":
        raise ValueError("Decida a classe semanticamente antes de executar SAM.")
    x, y, w, h = regiao["caixa"]
    altura, largura = rgb.shape[:2]
    box = [
        max(0, x - 3),
        max(0, y - 3),
        min(largura - 1, x + w + 3),
        min(altura - 1, y + h + 3),
    ]
    ys, xs = np.where(labels == regiao["id"])
    distancia = (xs - xs.mean()) ** 2 + (ys - ys.mean()) ** 2
    indice = int(np.argmin(distancia))
    ponto = [int(xs[indice]), int(ys[indice])]
    negativos = [[box[0], box[1]], [box[2], box[1]], [box[0], box[3]], [box[2], box[3]]]
    mascaras, scores, _ = predictor.predict(
        box=np.array(box),
        point_coords=np.array([ponto, *negativos]),
        point_labels=np.array([1, 0, 0, 0, 0]),
        multimask_output=True,
    )
    melhor = int(np.argmax(scores))
    return {
        "mascara_sam_rle": codificar_rle(mascaras[melhor]),
        "prompt_sam": {"caixa_xyxy": box, "positivo": ponto, "negativos": negativos},
        "score_sam": float(scores[melhor]),
        "revisao_silhueta": "pendente",
    }


def executar(fonte: Path, pasta: Path, checkpoint: Path) -> None:
    """Atualiza somente as propostas explicitamente solicitadas nas anotações."""
    imagem = fonte / "imagens" / (pasta.name + ".png")
    rgb = np.array(Image.open(imagem).convert("RGB"))
    placa, estruturas, _ = carregar_estruturas(pasta / "estruturas.json", imagem)
    arquivo = pasta / "regioes.json"
    dados = json.loads(arquivo.read_text("utf-8"))
    labels, inventario = inventariar(rgb, placa, estruturas, dados["regioes"])
    validar_inventario(dados["regioes"], inventario)
    wrapper = _carregar_sam(checkpoint)
    wrapper.set_image(rgb)
    try:
        for regiao in dados["regioes"]:
            if regiao.get("solicitar_sam"):
                regiao.update(segmentar(wrapper.preditor, rgb, labels, regiao))
                regiao.pop("solicitar_sam")
    finally:
        wrapper.reset_image()
    dados["checkpoint_sha256"] = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    arquivo.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fonte", type=Path, required=True)
    parser.add_argument("--anotacao", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    args = parser.parse_args()
    executar(args.fonte, args.anotacao, args.checkpoint)
