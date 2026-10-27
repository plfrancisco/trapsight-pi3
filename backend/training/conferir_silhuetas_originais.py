"""Mostra máscaras projetadas sobre o original para conferir divergências."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from training.estruturas_bases import restaurar_rle
from training.revisar_originais_ums import Transformacao
from training.teste_real_ums import _carregar_cartoes


def executar(
    originais: Path, anotacoes: Path, mapeamento: Path, auditoria: Path, saida: Path
) -> None:
    """Confere a máscara do modelo, sem usar a candidata escura como gabarito."""
    cartoes = {c.nome: c for c in _carregar_cartoes(originais)}
    mapa = json.loads(mapeamento.read_text("utf-8"))
    transformacoes = {
        p["placa"]: Transformacao(**p["transformacao"]) for p in mapa["placas"]
    }
    rel = json.loads(auditoria.read_text("utf-8"))
    itens = []
    for p in rel["placas"]:
        pasta = anotacoes / p["placa"]
        dados = json.loads((pasta / "regioes.json").read_text("utf-8"))
        t = transformacoes[p["placa"]]
        ids = p["medidas"]["regioes_inseto_com_silhueta_insuficiente"]
        if not ids:
            continue
        cartao = cartoes[p["placa"]]
        if not cartao.caminho.resolve().is_relative_to(originais.resolve()):
            raise ValueError("Original fora da raiz local confiável.")
        limite = Image.MAX_IMAGE_PIXELS
        try:
            Image.MAX_IMAGE_PIXELS = None
            with Image.open(cartao.caminho) as img:
                img.load()
                for r in dados["regioes"]:
                    if r["id"] not in ids:
                        continue
                    box = r["evidencia"]["recorte_original_xyxy"]
                    crop = np.array(img.crop(tuple(box)).convert("RGB"))
                    mascara = restaurar_rle(r.get("mascara_sam_rle", []), (576, 768))
                    sx, sy = (
                        t.largura_conteudo / t.altura,
                        t.altura_conteudo / t.largura,
                    )
                    m = np.array(
                        [
                            [0, sx, t.offset_x + (box[1] + 0.5) * sx - 0.5],
                            [
                                -sy,
                                0,
                                t.offset_y + (t.largura - box[0] - 0.5) * sy - 0.5,
                            ],
                        ]
                    )
                    local = cv2.warpAffine(
                        mascara.astype(np.uint8),
                        cv2.invertAffineTransform(m),
                        (crop.shape[1], crop.shape[0]),
                        flags=cv2.INTER_NEAREST,
                    ).astype(bool)
                    visual = crop.copy()
                    visual[local] = (
                        visual[local] * 0.5 + np.array((255, 0, 50)) * 0.5
                    ).astype(np.uint8)
                    antes = (
                        Image.fromarray(crop)
                        .transpose(Image.Transpose.ROTATE_90)
                        .resize((128, 128))
                    )
                    depois = (
                        Image.fromarray(visual)
                        .transpose(Image.Transpose.ROTATE_90)
                        .resize((128, 128))
                    )
                    itens.append((p["placa"][-4:], r["id"], antes, depois))
        finally:
            Image.MAX_IMAGE_PIXELS = limite
    folha = Image.new("RGB", (1120, 170 * ((len(itens) + 3) // 4)), "white")
    draw = ImageDraw.Draw(folha)
    for i, (placa, indice, antes, depois) in enumerate(itens):
        x, y = (i % 4) * 280, (i // 4) * 170
        folha.paste(antes, (x, y + 20))
        folha.paste(depois, (x + 132, y + 20))
        draw.text(
            (x, y + 2), f"{placa} ID {indice}: original / mascara SAM", fill="black"
        )
    folha.save(saida)


def alternativas(originais: Path, anotacoes: Path, saida: Path) -> None:
    """Apresenta as três propostas nativas sem promover nenhuma por score."""
    cartoes = {c.nome: c for c in _carregar_cartoes(originais)}
    itens = []
    for pasta in sorted(anotacoes.iterdir()):
        dados = json.loads((pasta / "regioes.json").read_text("utf-8"))
        selecionadas = [r for r in dados["regioes"] if r.get("alternativas_sam")]
        if not selecionadas:
            continue
        limite = Image.MAX_IMAGE_PIXELS
        try:
            Image.MAX_IMAGE_PIXELS = None
            cartao = cartoes[pasta.name]
            if not cartao.caminho.resolve().is_relative_to(originais.resolve()):
                raise ValueError("Original fora da raiz confiável.")
            with Image.open(cartao.caminho) as img:
                img.load()
                for r in selecionadas:
                    box = r["prompt_sam"]["recorte_original_xyxy"]
                    crop = np.array(img.crop(tuple(box)).convert("RGB"))
                    px, py = r["prompt_sam"]["ponto_local"]
                    zx, zy = max(0, round(px) - 128), max(0, round(py) - 128)
                    zoom = (
                        zx,
                        zy,
                        min(crop.shape[1], zx + 256),
                        min(crop.shape[0], zy + 256),
                    )
                    figuras = [Image.fromarray(crop).crop(zoom)]
                    for a in r["alternativas_sam"]:
                        local = restaurar_rle(a["nativa_rle"], crop.shape[:2])
                        vis = crop.copy()
                        vis[local] = (
                            vis[local] * 0.45 + np.array((255, 0, 50)) * 0.55
                        ).astype(np.uint8)
                        figuras.append(Image.fromarray(vis).crop(zoom))
                    figuras = [
                        f.transpose(Image.Transpose.ROTATE_90).resize((128, 128))
                        for f in figuras
                    ]
                    itens.append(
                        (
                            pasta.name[-4:],
                            r["id"],
                            figuras,
                            [a["score"] for a in r["alternativas_sam"]],
                        )
                    )
        finally:
            Image.MAX_IMAGE_PIXELS = limite
    folha = Image.new("RGB", (1088, 172 * ((len(itens) + 1) // 2)), "white")
    draw = ImageDraw.Draw(folha)
    for i, (placa, indice, figuras, scores) in enumerate(itens):
        x, y = (i % 2) * 544, (i // 2) * 172
        draw.text((x, y + 1), f"{placa} ID {indice} original / 0 / 1 / 2", fill="black")
        for j, f in enumerate(figuras):
            folha.paste(f, (x + j * 132, y + 18))
        draw.text(
            (x, y + 150),
            "scores: " + ", ".join(f"{s:.3f}" for s in scores),
            fill="black",
        )
    folha.save(saida)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for campo in ("originais", "anotacoes", "saida"):
        p.add_argument("--" + campo, type=Path, required=True)
    p.add_argument("--mapeamento", type=Path)
    p.add_argument("--auditoria", type=Path)
    p.add_argument("--alternativas", action="store_true")
    a = p.parse_args()
    if a.alternativas:
        alternativas(a.originais, a.anotacoes, a.saida)
    else:
        if not a.mapeamento or not a.auditoria:
            p.error("Informe --mapeamento e --auditoria.")
        executar(a.originais, a.anotacoes, a.mapeamento, a.auditoria, a.saida)
