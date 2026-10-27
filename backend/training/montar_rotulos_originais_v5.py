"""Aplica a política de rótulos v5 às máscaras segmentadas por caixa COCO."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

from training.dataset_sintetico import NOMES_BASES_REAIS
from training.estruturas_bases import (
    carregar_estruturas,
    inventariar,
    validar_inventario,
)
from training.medicoes_recomposicao import cinza_fixo
from training.segmentar_regioes_revisadas import codificar_rle

VERSAO = "mascaras_originais_v5"
LIMITE_IGNORADA_BASE_PP = 1.0
KERNEL_GRADE_MINIMO = 24
LARGURA = 768
ALTURA = 576


def hash_arquivo(caminho: Path) -> str:
    """Calcula SHA-256 sem ler o arquivo inteiro de uma vez."""
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def mascara_estruturas_geometricas(
    rgb: np.ndarray, placa: np.ndarray, caixa_bordas: int = 3
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Propõe grade e contorno por geometria linear, sem classificar insetos."""
    cinza = cinza_fixo(rgb)
    superficie = placa.astype(bool)
    tons = cinza[superficie]
    corte = float(np.median(tons) - 70) if tons.size else 80.0
    escuros = (cinza < corte).astype(np.uint8)
    largura = max(KERNEL_GRADE_MINIMO, LARGURA // 24)
    altura = max(KERNEL_GRADE_MINIMO, ALTURA // 24)
    horizontal = cv2.morphologyEx(
        escuros,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (largura, 1)),
    ).astype(bool)
    vertical = cv2.morphologyEx(
        escuros,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (1, altura)),
    ).astype(bool)
    grade = (horizontal | vertical) & superficie
    erodida = cv2.erode(
        superficie.astype(np.uint8),
        cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (caixa_bordas * 2 + 1, caixa_bordas * 2 + 1)
        ),
    ).astype(bool)
    borda = superficie & ~erodida
    return grade | borda, {"grade": grade, "borda": borda}


def caixa_modelo(
    bbox: list[float], transformacao: dict[str, int]
) -> tuple[int, int, int, int]:
    """Projeta os quatro cantos de uma caixa COCO à grade 768×576."""
    largura = transformacao["largura"]
    altura = transformacao["altura"]
    sx = transformacao["largura_conteudo"] / altura
    sy = transformacao["altura_conteudo"] / largura
    offset_x = transformacao["offset_x"]
    offset_y = transformacao["offset_y"]
    x, y, w, h = bbox
    pontos = [
        (offset_x + py * sx, offset_y + (largura - px) * sy)
        for px, py in ((x, y), (x + w, y), (x, y + h), (x + w, y + h))
    ]
    return (
        max(0, int(np.floor(min(p[0] for p in pontos)))),
        max(0, int(np.floor(min(p[1] for p in pontos)))),
        min(LARGURA, int(np.ceil(max(p[0] for p in pontos)))),
        min(ALTURA, int(np.ceil(max(p[1] for p in pontos)))),
    )


def candidatos_sem_coco(
    rgb: np.ndarray,
    placa: np.ndarray,
    estruturas: np.ndarray,
    caixas_coco: list[list[float]],
    transformacao: dict[str, int],
) -> np.ndarray:
    """Localiza regiões não anotadas para ignorá-las, sem atribuir a classe."""
    superficie = placa.astype(bool) & ~estruturas.astype(bool)
    if not superficie.any():
        return np.zeros((ALTURA, LARGURA), dtype=bool)
    cinza = cinza_fixo(rgb)
    candidatas = superficie & (cinza < float(np.median(cinza[superficie]) - 35))
    conhecidas = np.zeros_like(candidatas)
    for bbox in caixas_coco:
        x0, y0, x1, y1 = caixa_modelo(bbox, transformacao)
        if x1 > x0 and y1 > y0:
            conhecidas[y0:y1, x0:x1] = True
    return candidatas & ~conhecidas


def aplicar_politica(
    mascara: np.ndarray,
    placa: np.ndarray,
    regioes: list[dict[str, Any]],
    labels_candidatas: np.ndarray,
    candidatas_sem_coco: np.ndarray,
    p_maior_que_limite: bool,
    origem_base: bool,
) -> np.ndarray:
    """Preserva sujeira 1, ignora falhas COCO e protege silhuetas aceitas 2."""
    resultado = mascara.astype(np.uint8).copy()
    aceita = resultado == 2
    ignorar = resultado == 255
    if origem_base:
        for regiao in regioes:
            if regiao.get("evidencia", {}).get("coco"):
                continue
            pixels = labels_candidatas == int(regiao["id"])
            decisao = regiao.get("decisao")
            if decisao == "inseto":
                aceita |= pixels & placa
            elif decisao == "sujeira":
                resultado[pixels & placa] = 1
            elif decisao == "ambigua" or p_maior_que_limite:
                ignorar |= pixels
    elif p_maior_que_limite:
        ignorar |= candidatas_sem_coco
    ignorar |= resultado == 255
    ignorar &= placa
    resultado[placa] = 1
    resultado[ignorar & ~aceita] = 255
    resultado[aceita & placa] = 2
    resultado[~placa] = 0
    return resultado


def executar(
    reduzidas: Path,
    anotacoes: Path,
    segmentacao: Path,
    auditoria: Path,
    saida: Path,
) -> dict[str, Any]:
    """Gera versões finais das 69 máscaras e avalia elegibilidade das bases."""
    dados_auditoria = json.loads((auditoria / "auditoria.json").read_text("utf-8"))
    p = float(dados_auditoria["p_insetos_confirmados"])
    p_maior = p > float(dados_auditoria["limiar_p"])
    arquivos_registro = sorted((segmentacao / "registros").glob("*.json"))
    if len(arquivos_registro) != 69:
        raise ValueError(
            f"Esperadas 69 placas segmentadas; encontradas {len(arquivos_registro)}."
        )
    bases = {Path(nome).stem for nome in NOMES_BASES_REAIS}
    pasta_mascaras_finais = saida / "mascaras_final"
    pasta_decisoes = saida / "decisoes"
    (saida / "estruturas").mkdir(parents=True, exist_ok=True)
    pasta_mascaras_finais.mkdir(parents=True, exist_ok=True)
    pasta_decisoes.mkdir(parents=True, exist_ok=True)
    placas = []
    for arquivo in arquivos_registro:
        registro = json.loads(arquivo.read_text("utf-8"))
        nome = registro["placa"]
        imagem_path = reduzidas / "imagens" / f"{nome}.png"
        mascara_original_path = reduzidas / "mascaras" / f"{nome}.png"
        mascara_sam_path = segmentacao / "mascaras" / f"{nome}.png"
        rgb = np.asarray(Image.open(imagem_path).convert("RGB"))
        original = np.asarray(
            Image.open(mascara_original_path).convert("L"), dtype=np.uint8
        )
        mascara = np.asarray(Image.open(mascara_sam_path).convert("L"), dtype=np.uint8)
        estrutura_json = anotacoes / nome / "estruturas.json"
        documento_regioes = None
        labels_regioes = np.zeros((ALTURA, LARGURA), dtype=np.int32)
        regioes = []
        if nome in bases and estrutura_json.is_file():
            placa, estruturas, estrutura_dados = carregar_estruturas(
                estrutura_json, imagem_path
            )
            documento_regioes = json.loads(
                (anotacoes / nome / "regioes.json").read_text("utf-8")
            )
            regioes = documento_regioes["regioes"]
            labels_regioes, inventario = inventariar(rgb, placa, estruturas, regioes)
            validar_inventario(regioes, inventario)
            saida_estruturas = {
                **estrutura_dados,
                "mascara_fonte_sha256": hash_arquivo(mascara_original_path),
                "versao_rotulos": VERSAO,
                "revisao_visual": estrutura_dados.get("revisao_visual", "aprovada"),
            }
        else:
            placa = (original > 0) | (mascara == 2) | (mascara == 255)
            estruturas, categorias = mascara_estruturas_geometricas(rgb, placa)
            saida_estruturas = {
                "versao": "estruturas_geometricas_v1",
                "placa": nome,
                "imagem_sha256": hash_arquivo(imagem_path),
                "mascara_fonte_sha256": hash_arquivo(mascara_original_path),
                "estruturas_rle": codificar_rle(estruturas),
                "categorias_rle": {
                    categoria: codificar_rle(mascara_categoria)
                    for categoria, mascara_categoria in categorias.items()
                },
                "revisao_visual": "pendente",
                "uso": "somente fonte de recortes ou avaliação; estruturas não alteram a classe positiva SAM",
            }
        caixas = [item["bbox_original_xywh"] for item in registro["anotacoes"]]
        candidatos = candidatos_sem_coco(
            rgb,
            placa,
            estruturas,
            caixas,
            registro["transformacao"],
        )
        final = aplicar_politica(
            mascara,
            placa,
            regioes,
            labels_regioes,
            candidatos,
            p_maior,
            nome in bases,
        )
        destino = pasta_mascaras_finais / f"{nome}.png"
        Image.fromarray(final, "L").save(destino, format="PNG", optimize=True)
        area_placa = int(placa.sum())
        area_255 = int(np.count_nonzero(final == 255))
        percentual_255 = 100.0 * area_255 / max(1, area_placa)
        percentual_cobertura = (
            100.0
            * np.count_nonzero(final == 2)
            / max(1, int(np.count_nonzero((final == 1) | (final == 2))))
        )
        sem_decisao = sum(1 for regiao in regioes if not regiao.get("decisao"))
        base_elegivel = (
            nome in bases
            and sem_decisao == 0
            and percentual_255 <= LIMITE_IGNORADA_BASE_PP
        )
        if nome not in bases:
            base_elegivel = False
        caminho_estrutura = saida / "estruturas" / f"{nome}.json"
        caminho_estrutura.write_text(
            json.dumps(saida_estruturas, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        caminho_decisao = pasta_decisoes / f"{nome}.json"
        decisao = {
            "versao": VERSAO,
            "placa": nome,
            "sha256_original": registro["sha256_original"],
            "sha256_mascara_origem": hash_arquivo(mascara_original_path),
            "sha256_mascara_sam": hash_arquivo(mascara_sam_path),
            "sha256_mascara_final": hash_arquivo(destino),
            "p_insetos_confirmados": p,
            "p_ic95_wilson": dados_auditoria.get("p_insetos_confirmados_ic95_wilson"),
            "regioes_sem_decisao": sem_decisao,
            "classes_px": {
                str(classe): int(np.count_nonzero(final == classe))
                for classe in (0, 1, 2, 255)
            },
            "area_255_px": area_255,
            "area_placa_px": area_placa,
            "area_255_pp": percentual_255,
            "base_elegivel": base_elegivel,
            "revisao_visual": "aprovada" if nome in bases else "pendente",
        }
        caminho_decisao.write_text(
            json.dumps(decisao, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        placas.append(
            {
                "placa": nome,
                "sha256_original": registro["sha256_original"],
                "sha256_mascara_coco": hash_arquivo(mascara_sam_path),
                "sha256_complementar": hash_arquivo(destino),
                "sha256_estruturas": hash_arquivo(caminho_estrutura),
                "sha256_decisoes": hash_arquivo(caminho_decisao),
                "caixas_coco": registro["caixas_coco"],
                "mascaras_sam_aprovadas": registro["mascaras_aprovadas"],
                "mascaras_sam_reprovadas": registro["mascaras_reprovadas"],
                "taxa_aprovacao_sam": registro["taxa_aprovacao"],
                "area_255_px": area_255,
                "area_placa_px": area_placa,
                "area_255_pp": percentual_255,
                "percentual_cobertura_classe_2": percentual_cobertura,
                "regioes_sem_decisao": sem_decisao,
                "candidatos_sem_coco_nao_anotados_px": int(candidatos.sum()),
                "base_elegivel": base_elegivel,
                "medidas": {
                    "aceita": base_elegivel,
                    "regioes": {"sem_decisao": sem_decisao},
                    "area_255_pp": percentual_255,
                    "limite_area_255_pp": LIMITE_IGNORADA_BASE_PP,
                },
                "revisao_visual": "aprovada" if nome in bases else "pendente",
            }
        )
        print(
            f"{nome}: SAM {registro['mascaras_aprovadas']}/{registro['caixas_coco']}, "
            f"255 {percentual_255:.3f} pp, cobertura {percentual_cobertura:.2f}%",
            flush=True,
        )
    elegiveis = sum(placa["base_elegivel"] for placa in placas)
    manifesto = {
        "versao": "bases_semanticas_v5",
        "revisao_visual": "parcialmente_aprovada",
        "politica_sem_coco": {
            "p_estimado": p,
            "p_limite": dados_auditoria["limiar_p"],
            "quando_p_maior": "insetos não anotados e regiões ambíguas recebem 255; sujeira confirmada permanece 1",
        },
        "limite_base_255_pp": LIMITE_IGNORADA_BASE_PP,
        "bases_elegiveis": [
            placa["placa"] for placa in placas if placa["base_elegivel"]
        ],
        "quantidade_bases_elegiveis": elegiveis,
        "limiar_p": dados_auditoria["limiar_p"],
        "amostra_auditoria": dados_auditoria["amostra"],
        "auditoria_decisoes": dados_auditoria["decisoes"],
        "p_insetos_confirmados_ic95_wilson": dados_auditoria.get(
            "p_insetos_confirmados_ic95_wilson"
        ),
        "bases_nao_elegiveis": [
            {
                "placa": placa["placa"],
                "area_255_pp": placa["area_255_pp"],
                "limite": LIMITE_IGNORADA_BASE_PP,
            }
            for placa in placas
            if placa["placa"] in bases and not placa["base_elegivel"]
        ],
        "placas": placas,
        "aceite_por_area": elegiveis > 0,
        "avaliacao_real": "14 placas reservadas e nunca usadas na geração; regiões sem COCO ou rejeitadas pelo QC ficam em 255.",
        "limitacao": "Áreas em 255 não são avaliadas. As 14 imagens reais continuam sem gabarito de objetos fora das caixas COCO.",
    }
    (saida / "configuracao.json").write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifesto


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reduzidas", type=Path, required=True)
    parser.add_argument("--anotacoes", type=Path, required=True)
    parser.add_argument("--segmentacao", type=Path, required=True)
    parser.add_argument("--auditoria", type=Path, required=True)
    parser.add_argument("--saida", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(executar(**vars(args)), ensure_ascii=False))
