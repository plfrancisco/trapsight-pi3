"""Completa máscaras de bases usando SAM com caixas de manchas detectadas.

Os arquivos de origem são somente leitura. A classe 255 identifica propostas
ambíguas: conta como resolvida, sem ser contabilizada como inseto.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from training.dataset_sintetico import NOMES_BASES_REAIS
from training.teste_real_ums import Caixa, _carregar_sam

VERSAO = "sam_manchas_v4_revisada"
AREA_MINIMA = 12


def detectar_manchas(rgb: np.ndarray, classes: np.ndarray):
    """Protocolo fixo de revisão: mediana-35, área >=12 e filtro de forma."""
    placa = np.isin(classes, (1, 2, 255))
    r, g, b = (rgb[..., i].astype(np.int64) for i in range(3))
    cinza = ((r * 4899 + g * 9617 + b * 1868 + 8192) >> 14).astype(np.uint8)
    escura = (cinza < float(np.median(cinza[placa])) - 35) & placa
    _, rotulos, estatisticas, _ = cv2.connectedComponentsWithStats(
        escura.astype(np.uint8)
    )
    return rotulos, [
        (i, s)
        for i, s in enumerate(estatisticas)
        if i
        and s[4] >= AREA_MINIMA
        and max(s[2], s[3]) <= 60
        and max(s[2], s[3]) / min(s[2], s[3]) <= 6
    ]


def medir_completude(rgb: np.ndarray, classes: np.ndarray) -> dict[str, int | float]:
    """Conta classes 2, 255 e não resolvidas pelo mesmo inventário de manchas."""
    rotulos, manchas = detectar_manchas(rgb, classes)
    cobertas = ignoradas = 0
    for i, _ in manchas:
        pixels = classes[rotulos == i]
        if np.mean(pixels == 2) >= 0.5:
            cobertas += 1
        elif np.mean(pixels == 255) >= 0.5:
            ignoradas += 1
    nao_resolvidas = len(manchas) - cobertas - ignoradas
    return {
        "manchas": len(manchas),
        "rotuladas": cobertas,
        "ignoradas": ignoradas,
        "nao_resolvidas": nao_resolvidas,
        "completude": (cobertas + ignoradas) / max(1, len(manchas)),
    }


def completar(
    rgb: np.ndarray, original: np.ndarray, preditor, ignorar: set[int] | None = None
):
    """Segmenta cada mancha no embedding da imagem e registra a decisão."""
    resultado = original.copy()
    rotulos, manchas = detectar_manchas(rgb, original)
    altura, largura = original.shape
    preditor.set_image(rgb)
    ids_validos = {i for i, _ in manchas}
    if (ignorar or set()) - ids_validos:
        raise ValueError("A revisão referencia componentes ausentes do inventário.")
    decisoes = []
    for indice, stats in manchas:
        x, y, w, h, area = map(int, stats)
        componente = rotulos == indice
        caixa = Caixa(
            max(0, x - 1),
            max(0, y - 1),
            min(largura, x + w + 1),
            min(altura, y + h + 1),
        )
        roi = (
            max(0, x - 4),
            max(0, y - 4),
            min(largura, x + w + 4),
            min(altura, y + h + 4),
        )
        x0, y0, x1, y1 = roi
        local = componente[y0:y1, x0:x1]
        if indice in (ignorar or set()):
            proposta, score = np.zeros_like(local), 0.0
        else:
            proposta, score = preditor.segmentar_recorte(caixa, roi)
        proposta = proposta & np.isin(original[y0:y1, x0:x1], (1, 2))
        sobreposicao = int((proposta & local).sum()) / area
        aceita = (
            score >= 0.75
            and sobreposicao >= 0.5
            and 0 < proposta.sum() <= max(25, area * 5)
        )
        regiao = resultado[y0:y1, x0:x1]
        if aceita:
            regiao[proposta] = 2
            decisao = "sam_aceita"
        else:
            ambiguo = cv2.dilate(
                local.astype(np.uint8), np.ones((3, 3), np.uint8)
            ).astype(bool)
            if indice in (ignorar or set()):
                regiao[ambiguo & (original[y0:y1, x0:x1] > 0)] = 255
                decisao = "ignorada_revisao_visual"
            else:
                regiao[ambiguo & (regiao == 1)] = 255
                decisao = "ignorada_ambigua"
        decisoes.append(
            {
                "indice": indice,
                "caixa": [x, y, w, h],
                "area": area,
                "score_sam": float(score),
                "sobreposicao_mancha": sobreposicao,
                "decisao": decisao,
            }
        )
    preditor.reset_image()
    return resultado, decisoes


def executar(
    fonte: Path, saida: Path, checkpoint: Path, revisao: Path | None = None
) -> dict:
    """Grava máscaras complementares, auditoria de caixas e painéis para revisão."""
    if saida.exists() and any(saida.iterdir()):
        raise FileExistsError(f"A saída precisa ser nova: {saida}")
    pasta = saida / "mascaras"
    pasta.mkdir(parents=True)
    preditor = _carregar_sam(checkpoint)
    anotacoes = json.loads(revisao.read_text("utf-8")) if revisao else {"placas": {}}
    registros = []
    for nome in NOMES_BASES_REAIS:
        rgb = np.array(Image.open(fonte / "imagens" / nome).convert("RGB"))
        original_path = fonte / "mascaras" / nome
        original = np.array(Image.open(original_path).convert("L"))
        if rgb.shape[:2] != (576, 768) or original.shape != (576, 768):
            raise ValueError("A revisão das bases exige os arquivos nativos 768x576.")
        anotacao = anotacoes["placas"].get(Path(nome).stem, {})
        if (
            anotacao
            and hashlib.sha256(original_path.read_bytes()).hexdigest()
            != anotacao["sha256_original"]
        ):
            raise ValueError(f"A máscara original mudou desde a revisão: {nome}")
        nova, decisoes = completar(
            rgb, original, preditor, set(anotacao.get("ignorar_componentes", []))
        )
        Image.fromarray(nova).save(pasta / nome)
        visual = rgb.copy()
        for classe, cor in ((2, (255, 0, 70)), (255, (255, 190, 0))):
            selecionada = nova == classe
            visual[selecionada] = (
                visual[selecionada] * 0.5 + np.array(cor) * 0.5
            ).astype(np.uint8)
        Image.fromarray(visual).save(saida / f"revisao_{nome}")
        # Todos os componentes podem ser inspecionados ampliados, com decisão e caixa.
        painel = Image.new("RGB", (12 * 80, ((len(decisoes) + 11) // 12) * 96), "white")
        desenho = ImageDraw.Draw(painel)
        for j, decisao in enumerate(decisoes):
            x, y, w, h = decisao["caixa"]
            crop = Image.fromarray(rgb).crop(
                (
                    max(0, x - 5),
                    max(0, y - 5),
                    min(rgb.shape[1], x + w + 5),
                    min(rgb.shape[0], y + h + 5),
                )
            )
            crop.thumbnail((76, 70))
            crop = crop.resize((76, 70), Image.Resampling.NEAREST)
            xx, yy = (j % 12) * 80, (j // 12) * 96
            painel.paste(crop, (xx, yy))
            desenho.text(
                (xx, yy + 71),
                f"{decisao['indice']} {decisao['score_sam']:.2f}",
                fill="black",
            )
            desenho.text(
                (xx, yy + 82),
                "SAM" if decisao["decisao"] == "sam_aceita" else "IGN",
                fill="black",
            )
        painel.save(saida / f"componentes_{nome}")
        registros.append(
            {
                "placa": Path(nome).stem,
                "antes": medir_completude(rgb, original),
                "depois": medir_completude(rgb, nova),
                "sha256_original": hashlib.sha256(
                    original_path.read_bytes()
                ).hexdigest(),
                "sha256_complementar": hashlib.sha256(
                    (pasta / nome).read_bytes()
                ).hexdigest(),
                "pixels_ignorados": int(np.count_nonzero(nova == 255)),
                "decisoes": decisoes,
            }
        )
        print(nome, registros[-1]["antes"], registros[-1]["depois"], flush=True)
    relatorio = {
        "versao": VERSAO,
        "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "protocolo": {
            "cinza_menor_que": "mediana(cinza na máscara original >=1)-35",
            "area_minima_px": AREA_MINIMA,
            "maior_lado_maximo": 60,
            "razao_lados_maxima": 6,
            "conectividade": 8,
            "rotulada": ">=50% na classe 2",
            "ignorada": ">=50% na classe 255",
            "ignorada_conta_rotulada": False,
            "sucesso": "no máximo 10% de manchas não resolvidas",
        },
        "revisao_visual": "aprovada" if revisao else "pendente",
        "anotacoes_revisao": anotacoes,
        "placas": registros,
    }
    (saida / "configuracao.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return relatorio


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fonte", type=Path, required=True)
    parser.add_argument("--saida", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--revisao", type=Path)
    args = parser.parse_args()
    executar(args.fonte, args.saida, args.checkpoint, args.revisao)
