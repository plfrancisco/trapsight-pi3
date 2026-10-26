"""Medições de imagem com a mesma régua nas placas reais e nas composições."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

FAIXAS_ESCURO = ((0, 0.5), (0.5, 1), (1, 2), (2, 4), (4, 8), (8, 100.01))


def cinza_fixo(rgb: np.ndarray) -> np.ndarray:
    """Conversão RGB em ponto fixo, independente da versão do OpenCV."""
    r, g, b = (rgb[..., i].astype(np.int64) for i in range(3))
    return ((4899 * r + 9617 * g + 1868 * b + 8192) >> 14).astype(np.uint8)


def linhas_longas(binario: np.ndarray, comprimento: int = 41) -> np.ndarray:
    """Pixels de segmentos retos horizontais/verticais com pelo menos 41 px."""
    dados = binario.astype(np.uint8)
    horizontal = cv2.morphologyEx(
        dados,
        cv2.MORPH_OPEN,
        np.ones((1, comprimento), np.uint8),
        borderType=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    vertical = cv2.morphologyEx(
        dados,
        cv2.MORPH_OPEN,
        np.ones((comprimento, 1), np.uint8),
        borderType=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    return (horizontal | vertical).astype(bool)


def medir_espalhamento(
    rgb: np.ndarray, mascara: np.ndarray, sem_grade: bool = True
) -> dict[str, float | int]:
    """Escuro <110, aglomeração >500 px e ocupação em tiles de 24 px.

    Tiles precisam conter pelo menos metade da área válida da placa. Pixels
    255 e fundo não participam de numeradores nem denominadores.
    """
    placa = np.isin(mascara, (1, 2))
    escuro = (cinza_fixo(rgb) < 110) & placa
    if sem_grade:
        escuro &= ~linhas_longas(escuro)
    n, _, stats, _ = cv2.connectedComponentsWithStats(
        escuro.astype(np.uint8), connectivity=8
    )
    area_escura = int(escuro.sum())
    area_grande = sum(
        int(stats[i, cv2.CC_STAT_AREA])
        for i in range(1, n)
        if stats[i, cv2.CC_STAT_AREA] > 500
    )
    elegiveis = ocupados = 0
    h, w = placa.shape
    for y in range(0, h - 23, 24):
        for x in range(0, w - 23, 24):
            if placa[y : y + 24, x : x + 24].mean() < 0.5:
                continue
            elegiveis += 1
            ocupados += int(escuro[y : y + 24, x : x + 24].sum() >= 3)
    return {
        "pixels_placa": int(placa.sum()),
        "pixels_escuros": area_escura,
        "fracao_escura": area_escura / max(1, int(placa.sum())),
        "aglomeracao": area_grande / max(1, area_escura),
        "ocupacao": ocupados / max(1, elegiveis),
        "tiles_elegiveis": elegiveis,
    }


def agrupar_por_escuro(medicoes: list[dict]) -> dict:
    """Médias estratificadas pela densidade escura, sem misturar coberturas."""
    saida = {}
    for minimo, maximo in FAIXAS_ESCURO:
        grupo = [m for m in medicoes if minimo <= 100 * m["fracao_escura"] < maximo]
        saida[f"{minimo:g}-{maximo:g}%"] = {
            "amostras": len(grupo),
            **{
                campo: float(np.mean([m[campo] for m in grupo])) if grupo else None
                for campo in ("fracao_escura", "aglomeracao", "ocupacao")
            },
        }
    return saida


def medir_dataset(pasta: Path) -> dict:
    """Aplica o protocolo às imagens e máscaras pareadas, sem alterar arquivos."""
    registros = []
    for arquivo in sorted((pasta / "imagens").glob("*.png")):
        rgb = np.array(Image.open(arquivo).convert("RGB"))
        mascara = np.array(Image.open(pasta / "mascaras" / arquivo.name))
        if rgb.shape[:2] != mascara.shape or not np.isin(mascara, (0, 1, 2, 255)).all():
            raise ValueError(f"Par inválido: {arquivo.name}")
        registros.append(
            {
                "id": arquivo.stem,
                "com_grade": medir_espalhamento(rgb, mascara, False),
                "sem_grade": medir_espalhamento(rgb, mascara, True),
            }
        )
    if not registros:
        raise ValueError("Nenhum par PNG encontrado no dataset.")
    return {
        "placas": len(registros),
        "aglomeracao_com_grade": float(
            np.mean([r["com_grade"]["aglomeracao"] for r in registros])
        ),
        "aglomeracao_sem_grade": float(
            np.mean([r["sem_grade"]["aglomeracao"] for r in registros])
        ),
        "sem_grade_por_faixa": agrupar_por_escuro([r["sem_grade"] for r in registros]),
        "registros": registros,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--saida", type=Path, required=True)
    args = parser.parse_args()
    resultado = medir_dataset(args.dataset)
    args.saida.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {k: v for k, v in resultado.items() if k != "registros"},
            ensure_ascii=False,
            indent=2,
        )
    )
