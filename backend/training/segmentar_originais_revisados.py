"""Segmenta recortes nativos de insetos previamente reconhecidos na revisão.

As candidatas só fornecem caixas e pontos para SAM. A saída nunca altera a
decisão semântica e é projetada geometricamente para a resolução do modelo.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from training.estruturas_bases import carregar_estruturas, inventariar
from training.revisar_originais_ums import Transformacao
from training.segmentar_regioes_revisadas import codificar_rle
from training.teste_real_ums import _carregar_cartoes, _carregar_sam


def projetar(mascara: np.ndarray, recorte: list[int], t: Transformacao) -> np.ndarray:
    """Projeta centros de pixels, respeitando rotação e margens do produtor."""
    x0, y0, _, _ = recorte
    sx, sy = t.largura_conteudo / t.altura, t.altura_conteudo / t.largura
    matriz = np.array(
        [
            [0, sx, t.offset_x + (y0 + 0.5) * sx - 0.5],
            [-sy, 0, t.offset_y + (t.largura - x0 - 0.5) * sy - 0.5],
        ],
        np.float64,
    )
    return cv2.warpAffine(
        mascara.astype(np.uint8), matriz, (768, 576), flags=cv2.INTER_NEAREST
    ).astype(bool)


def executar(
    originais: Path,
    reduzidas: Path,
    anotacoes: Path,
    mapeamento: Path,
    checkpoint: Path,
) -> None:
    """Abre uma placa por vez e agrupa prompts por pequenas janelas nativas."""
    cartoes = {c.nome: c for c in _carregar_cartoes(originais)}
    mapa = json.loads(mapeamento.read_text("utf-8"))
    transformacoes = {
        p["placa"]: Transformacao(**p["transformacao"]) for p in mapa["placas"]
    }
    wrapper = _carregar_sam(checkpoint)
    checkpoint_hash = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    for pasta in sorted(anotacoes.iterdir()):
        arquivo = pasta / "regioes.json"
        dados = json.loads(arquivo.read_text("utf-8"))
        solicitadas = [r for r in dados["regioes"] if r.get("solicitar_sam_original")]
        if not solicitadas:
            continue
        cartao = cartoes[pasta.name]
        if not cartao.caminho.resolve().is_relative_to(originais.resolve()):
            raise ValueError("Original fora da raiz confiável.")
        t = transformacoes[pasta.name]
        imagem_baixa = reduzidas / "imagens" / (pasta.name + ".png")
        rgb_baixa = np.array(Image.open(imagem_baixa).convert("RGB"))
        placa, estruturas, _ = carregar_estruturas(
            pasta / "estruturas.json", imagem_baixa
        )
        labels, _ = inventariar(rgb_baixa, placa, estruturas, dados["regioes"])
        grupos = {}
        for r in solicitadas:
            if r["decisao"] != "inseto":
                raise ValueError("SAM exige decisão prévia de inseto.")
            ys, xs = np.where(labels == r["id"])
            proximo = int(np.argmin((xs - xs.mean()) ** 2 + (ys - ys.mean()) ** 2))
            r["ponto_reduzido"] = [float(xs[proximo]) + 0.5, float(ys[proximo]) + 0.5]
            px, py = t.inverso(*r["ponto_reduzido"])
            grupos.setdefault((int(px) // 128, int(py) // 128), []).append(r)
        limite_anterior = Image.MAX_IMAGE_PIXELS
        try:
            Image.MAX_IMAGE_PIXELS = None
            with Image.open(cartao.caminho) as original:
                original.load()
                for (gx, gy), regioes in grupos.items():
                    x0, y0 = max(0, gx * 128 - 192), max(0, gy * 128 - 192)
                    recorte = [
                        x0,
                        y0,
                        min(original.width, x0 + 512),
                        min(original.height, y0 + 512),
                    ]
                    crop = original.crop(tuple(recorte)).convert("RGB")
                    rgb = np.array(crop)
                    wrapper.set_image(rgb)
                    for r in regioes:
                        x, y, w, h = r["caixa"]
                        px, py = t.inverso(*r["ponto_reduzido"])
                        xa, ya = t.inverso(x, y + h)
                        xb, yb = t.inverso(x + w, y)
                        box = [
                            max(0, min(xa, xb) - x0 - 24),
                            max(0, min(ya, yb) - y0 - 24),
                            min(crop.width - 1, max(xa, xb) - x0 + 24),
                            min(crop.height - 1, max(ya, yb) - y0 + 24),
                        ]
                        ponto = [
                            min(crop.width - 1, max(0, px - x0)),
                            min(crop.height - 1, max(0, py - y0)),
                        ]
                        negativos = [
                            [box[0], box[1]],
                            [box[2], box[1]],
                            [box[0], box[3]],
                            [box[2], box[3]],
                        ]
                        mascaras, scores, _ = wrapper.preditor.predict(
                            box=np.array(box),
                            point_coords=np.array([ponto, *negativos]),
                            point_labels=np.array([1, 0, 0, 0, 0]),
                            multimask_output=True,
                        )
                        candidatas = [
                            i
                            for i, m in enumerate(mascaras)
                            if m[round(ponto[1]), round(ponto[0])]
                            and m.sum() < 0.65 * m.size
                        ]
                        melhor = max(
                            candidatas or range(len(scores)),
                            key=lambda i: float(scores[i]),
                        )
                        if r.get("salvar_alternativas_sam"):
                            r["alternativas_sam"] = [
                                {
                                    "score": float(s),
                                    "nativa_rle": codificar_rle(m),
                                    "modelo_rle": codificar_rle(
                                        projetar(m, recorte, t)
                                    ),
                                }
                                for m, s in zip(mascaras, scores, strict=True)
                            ]
                        silhueta = mascaras[melhor]
                        r["mascara_sam_rle"] = codificar_rle(
                            projetar(silhueta, recorte, t)
                        )
                        r["prompt_sam"] = {
                            "escala": "original",
                            "recorte_original_xyxy": recorte,
                            "caixa_local_xyxy": box,
                            "ponto_local": ponto,
                            "negativos": negativos,
                        }
                        r["score_sam"] = float(scores[melhor])
                        r["revisao_silhueta"] = "pendente"
                        r["fracao_recorte_sam"] = float(silhueta.mean())
                        r.pop("solicitar_sam_original")
                    wrapper.reset_image()
                    crop.close()
        finally:
            Image.MAX_IMAGE_PIXELS = limite_anterior
        dados["checkpoint_sha256"] = checkpoint_hash
        arquivo.write_text(
            json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(pasta.name, "propostas nativas", len(solicitadas), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--originais", type=Path, required=True)
    p.add_argument("--reduzidas", type=Path, required=True)
    p.add_argument(
        "--anotacoes", type=Path, default=Path(__file__).with_name("anotacoes_ums")
    )
    p.add_argument("--mapeamento", type=Path, required=True)
    p.add_argument("--checkpoint", type=Path, required=True)
    a = p.parse_args()
    executar(a.originais, a.reduzidas, a.anotacoes, a.mapeamento, a.checkpoint)
