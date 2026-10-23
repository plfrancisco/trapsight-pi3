"""Monta um conjunto de avaliação real a partir das placas UMS e caixas COCO."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import re
import sys
import warnings
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

LARGURA_SAIDA = 768
ALTURA_SAIDA = 576
ESCALA_ENTRADA_PADRAO = 0.25
PX_POR_MM_FONTE = 23.62
SEMENTE_GLOBAL = 20261021
VALORES_CLASSES = {"fundo": 0, "placa_limpa": 1, "placa_coberta": 2}
FAIXAS_COBERTURA = (("ok", 10.0), ("atencao", 20.0), ("trocar", math.inf))
FONTE_PADRAO = Path(r"D:\dados\trapsight\dataset-real-ums\dados")
SAIDA_PADRAO = Path(r"D:\dados\trapsight\teste-real-ums")
CHECKPOINT_PADRAO = Path(r"D:\dados\trapsight\modelos-sam\sam_vit_b_01ec64.pth")


@dataclass(frozen=True)
class CartaoCOCO:
    """Imagem UMS e anotações associadas no formato COCO."""

    caminho: Path
    nome: str
    largura: int
    altura: int
    anotacoes: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class Caixa:
    """Retângulo em coordenadas de imagem, com borda final exclusiva."""

    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def largura(self) -> int:
        return max(0, self.x1 - self.x0)

    @property
    def altura(self) -> int:
        return max(0, self.y1 - self.y0)

    @property
    def area(self) -> int:
        return self.largura * self.altura


def transformar_caixa_rotacao_90(
    bbox: tuple[float, float, float, float],
    largura_original: int,
    escala_x: float,
    escala_y: float,
) -> Caixa:
    """Redimensiona uma caixa COCO e a gira 90 graus no sentido anti-horário."""
    x, y, largura, altura = bbox
    x0 = y * escala_y
    y0 = largura_original - (x + largura) * escala_x
    x1 = (y + altura) * escala_y
    y1 = largura_original - x * escala_x
    return Caixa(
        max(0, math.floor(x0)),
        max(0, math.floor(y0)),
        max(0, math.ceil(x1)),
        max(0, math.ceil(y1)),
    )


def _carregar_cartoes(diretorio: Path) -> list[CartaoCOCO]:
    raiz = diretorio.resolve()
    arquivos_json = sorted(raiz.rglob("instances_default.json"))
    if not arquivos_json:
        raise ValueError(f"Nenhum instances_default.json encontrado em {raiz}.")

    cartoes: list[CartaoCOCO] = []
    nomes: set[str] = set()
    for caminho_json in arquivos_json:
        try:
            documento = json.loads(caminho_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as erro:
            raise ValueError(f"Não foi possível ler {caminho_json}: {erro}.") from erro
        imagens = documento.get("images")
        anotacoes = documento.get("annotations")
        if not isinstance(imagens, list) or not isinstance(anotacoes, list):
            raise ValueError(f"O COCO {caminho_json} precisa listar imagens e caixas.")
        anotacoes_por_imagem: dict[int, list[dict[str, Any]]] = {}
        for anotacao in anotacoes:
            if not isinstance(anotacao, dict):
                continue
            imagem_id = anotacao.get("image_id")
            bbox = anotacao.get("bbox")
            if (
                isinstance(imagem_id, int)
                and isinstance(bbox, list)
                and len(bbox) == 4
                and all(isinstance(valor, (int, float)) for valor in bbox)
            ):
                anotacoes_por_imagem.setdefault(imagem_id, []).append(anotacao)

        for imagem in imagens:
            if not isinstance(imagem, dict):
                continue
            imagem_id = imagem.get("id")
            arquivo = imagem.get("file_name")
            largura = imagem.get("width")
            altura = imagem.get("height")
            if (
                not isinstance(imagem_id, int)
                or not isinstance(arquivo, str)
                or not isinstance(largura, int)
                or not isinstance(altura, int)
            ):
                raise ValueError(f"Metadados de imagem inválidos em {caminho_json}.")
            caminho_imagem = caminho_json.parent / Path(arquivo).name
            if not caminho_imagem.is_file():
                raise FileNotFoundError(f"Imagem COCO ausente: {caminho_imagem}.")
            nome = _identificador(caminho_json.parent.name, caminho_imagem.stem)
            if nome in nomes:
                raise ValueError(f"Identificador de cartão duplicado: {nome}.")
            nomes.add(nome)
            cartoes.append(
                CartaoCOCO(
                    caminho=caminho_imagem,
                    nome=nome,
                    largura=largura,
                    altura=altura,
                    anotacoes=tuple(anotacoes_por_imagem.get(imagem_id, ())),
                )
            )
    if not cartoes:
        raise ValueError("Os arquivos COCO não contêm imagens para avaliar.")
    return sorted(cartoes, key=lambda cartao: cartao.nome)


def _identificador(grupo: str, nome: str) -> str:
    bruto = f"{grupo}_{nome}".lower()
    seguro = re.sub(r"[^a-z0-9_-]+", "_", bruto).strip("_-")
    return seguro[:120]


def _abrir_reduzida(caminho: Path, escala: float) -> Image.Image:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", Image.DecompressionBombWarning)
        with Image.open(caminho) as original:
            largura_original, altura_original = original.size
            original.draft(
                "RGB",
                (
                    round(largura_original * escala),
                    round(altura_original * escala),
                ),
            )
            girada = original.convert("RGB").transpose(Image.Transpose.ROTATE_90)
            tamanho_saida = (
                round(altura_original * escala),
                round(largura_original * escala),
            )
            if girada.size != tamanho_saida:
                girada = girada.resize(tamanho_saida, Image.Resampling.LANCZOS)
            return girada


def _recortar_caixa(
    bbox: tuple[float, float, float, float],
    largura_original: int,
    altura_original: int,
    tamanho_reduzido: tuple[int, int],
) -> Caixa:
    escala_x = tamanho_reduzido[0] / largura_original
    escala_y = tamanho_reduzido[1] / altura_original
    caixa = transformar_caixa_rotacao_90(bbox, tamanho_reduzido[0], escala_x, escala_y)
    largura_girada, altura_girada = tamanho_reduzido[1], tamanho_reduzido[0]
    return Caixa(
        min(largura_girada, caixa.x0),
        min(altura_girada, caixa.y0),
        min(largura_girada, caixa.x1),
        min(altura_girada, caixa.y1),
    )


def _agrupar_projecao(projecao: np.ndarray, limiar: float) -> list[tuple[float, float]]:
    indices = np.flatnonzero(projecao >= limiar)
    if not len(indices):
        return []
    max_intervalo = max(1, round(len(projecao) * 0.001))
    grupos = np.split(indices, np.where(np.diff(indices) > max_intervalo)[0] + 1)
    linhas: list[tuple[float, float]] = []
    for grupo in grupos:
        if len(grupo) < 2:
            continue
        pesos = projecao[grupo].astype(np.float64)
        centro = float(np.average(grupo, weights=pesos))
        linhas.append((centro, float(pesos.max())))
    return linhas


def _selecionar_linhas_uniformes(
    candidatas: list[tuple[float, float]],
    quantidade: int,
    comprimento_eixo: int,
) -> tuple[float, ...] | None:
    if len(candidatas) < quantidade:
        return None
    melhor: tuple[float, tuple[float, ...]] | None = None
    for combinacao in itertools.combinations(candidatas, quantidade):
        centros = tuple(item[0] for item in combinacao)
        distancias = np.diff(centros)
        media = float(distancias.mean())
        if media < comprimento_eixo * 0.06 or media > comprimento_eixo * 0.3:
            continue
        variacao = float(distancias.std() / media)
        suporte = sum(item[1] for item in combinacao) / max(
            1.0, comprimento_eixo * quantidade
        )
        pontuacao = variacao - min(0.08, suporte * 0.01)
        if melhor is None or pontuacao < melhor[0]:
            melhor = (pontuacao, centros)
    return None if melhor is None else melhor[1]


def _detectar_caixa_placa(
    rgb: np.ndarray,
    caixas: list[Caixa],
) -> Caixa:
    """Localiza as linhas externas da grade, incluindo-as como placa limpa."""
    import cv2

    altura, largura = rgb.shape[:2]
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    cinza = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    escuro = (cinza < 120).astype(np.uint8) * 255
    horizontal = cv2.morphologyEx(
        escuro,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (max(20, largura // 20), 1)),
    )
    vertical = cv2.morphologyEx(
        escuro,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(20, altura // 20))),
    )
    linhas_y = _agrupar_projecao(
        (horizontal > 0).sum(axis=1), max(25.0, largura * 0.06)
    )
    linhas_x = _agrupar_projecao((vertical > 0).sum(axis=0), max(25.0, altura * 0.06))
    grade_x = _selecionar_linhas_uniformes(linhas_x, 7, largura)
    grade_y = _selecionar_linhas_uniformes(linhas_y, 4, altura)
    if grade_x is not None and grade_y is not None:
        return Caixa(
            max(0, math.floor(grade_x[0])),
            max(0, math.floor(grade_y[0])),
            min(largura, math.ceil(grade_x[-1]) + 1),
            min(altura, math.ceil(grade_y[-1]) + 1),
        )

    if grade_x is not None and len(linhas_y) >= 3:
        tres = _selecionar_linhas_uniformes(linhas_y, 3, altura)
        if tres is not None:
            passo = float(np.median(np.diff(tres)))
            candidatos_y = (
                (tres[0] - passo, tres[-1]),
                (tres[0], tres[-1] + passo),
            )
            min_caixas = min((caixa.y0 for caixa in caixas), default=0)
            max_caixas = max((caixa.y1 for caixa in caixas), default=altura)
            escolhida = min(
                candidatos_y,
                key=lambda limites: (
                    max(0.0, limites[0] - min_caixas)
                    + max(0.0, max_caixas - limites[1]),
                    abs((limites[0] + limites[1]) / 2 - altura / 2),
                ),
            )
            return Caixa(
                max(0, math.floor(grade_x[0])),
                max(0, math.floor(escolhida[0])),
                min(largura, math.ceil(grade_x[-1]) + 1),
                min(altura, math.ceil(escolhida[1]) + 1),
            )

    if not caixas:
        raise ValueError("Não foi possível localizar a grade nem há caixas COCO.")
    x0 = min(caixa.x0 for caixa in caixas)
    y0 = min(caixa.y0 for caixa in caixas)
    x1 = max(caixa.x1 for caixa in caixas)
    y1 = max(caixa.y1 for caixa in caixas)
    margem = max(4, round(max(x1 - x0, y1 - y0) * 0.12))
    x0, y0 = max(0, x0 - margem), max(0, y0 - margem)
    x1, y1 = min(largura, x1 + margem), min(altura, y1 + margem)
    proporcao = 450 / 220
    centro_x, centro_y = (x0 + x1) / 2, (y0 + y1) / 2
    if (x1 - x0) / max(1, y1 - y0) < proporcao:
        novo_largura = (y1 - y0) * proporcao
        x0, x1 = (
            max(0, round(centro_x - novo_largura / 2)),
            min(largura, round(centro_x + novo_largura / 2)),
        )
    else:
        nova_altura = (x1 - x0) / proporcao
        y0, y1 = (
            max(0, round(centro_y - nova_altura / 2)),
            min(altura, round(centro_y + nova_altura / 2)),
        )
    return Caixa(x0, y0, x1, y1)


def _criar_mascara_classes(
    tamanho: tuple[int, int],
    caixa_placa: Caixa,
    mascaras_insetos: list[np.ndarray],
) -> np.ndarray:
    """Combina placa limpa, grade e máscaras de inseto numa união binária."""
    largura, altura = tamanho
    resultado = np.zeros((altura, largura), dtype=np.uint8)
    resultado[caixa_placa.y0 : caixa_placa.y1, caixa_placa.x0 : caixa_placa.x1] = (
        VALORES_CLASSES["placa_limpa"]
    )
    if mascaras_insetos:
        uniao = np.logical_or.reduce(mascaras_insetos)
        regiao_placa = resultado == VALORES_CLASSES["placa_limpa"]
        resultado[uniao & regiao_placa] = VALORES_CLASSES["placa_coberta"]
    return resultado


def _resumo_areas(
    caixas: list[Caixa], areas_mascaras: list[int]
) -> dict[str, float | int]:
    soma_caixas = sum(caixa.area for caixa in caixas)
    soma_mascaras = sum(areas_mascaras)
    diferenca = soma_mascaras - soma_caixas
    return {
        "quantidade_caixas": len(caixas),
        "quantidade_mascaras": len(areas_mascaras),
        "soma_area_caixas_px": soma_caixas,
        "soma_area_mascaras_px": soma_mascaras,
        "diferenca_area_px": diferenca,
        "diferenca_relativa_percentual": (
            diferenca * 100.0 / soma_caixas if soma_caixas else 0.0
        ),
    }


def _preparar_saida(
    imagem: Image.Image, mascara: np.ndarray
) -> tuple[Image.Image, Image.Image, float]:
    largura, altura = imagem.size
    fator = min(LARGURA_SAIDA / largura, ALTURA_SAIDA / altura)
    nova_largura = max(1, round(largura * fator))
    nova_altura = max(1, round(altura * fator))
    imagem_reduzida = imagem.resize(
        (nova_largura, nova_altura), Image.Resampling.LANCZOS
    )
    mascara_reduzida = Image.fromarray(mascara, mode="L").resize(
        (nova_largura, nova_altura), Image.Resampling.NEAREST
    )
    imagem_final = Image.new("RGB", (LARGURA_SAIDA, ALTURA_SAIDA), (230, 235, 235))
    mascara_final = Image.new("L", (LARGURA_SAIDA, ALTURA_SAIDA), 0)
    deslocamento_x = (LARGURA_SAIDA - nova_largura) // 2
    deslocamento_y = (ALTURA_SAIDA - nova_altura) // 2
    imagem_final.paste(imagem_reduzida, (deslocamento_x, deslocamento_y))
    mascara_final.paste(mascara_reduzida, (deslocamento_x, deslocamento_y))
    return imagem_final, mascara_final, fator


def _percentual_cobertura(mascara: np.ndarray) -> float:
    area_placa = np.count_nonzero(
        (mascara == VALORES_CLASSES["placa_limpa"])
        | (mascara == VALORES_CLASSES["placa_coberta"])
    )
    area_coberta = np.count_nonzero(mascara == VALORES_CLASSES["placa_coberta"])
    return 100.0 * area_coberta / area_placa if area_placa else 0.0


def _faixa_status(percentual: float) -> str:
    for faixa, limite in FAIXAS_COBERTURA:
        if percentual < limite:
            return faixa
    return "trocar"


def _cor_fundo_lab(rgb: np.ndarray) -> np.ndarray:
    import cv2

    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    luminancia = lab[..., 0]
    limiar = float(np.percentile(luminancia, 40))
    claros = lab[luminancia >= limiar]
    return np.median(claros, axis=0) if len(claros) else np.median(lab, axis=(0, 1))


def _segmentar_anotacoes(
    rgb: np.ndarray,
    caixas: list[Caixa],
    caixa_placa: Caixa,
    preditor: Any,
) -> tuple[list[np.ndarray], list[int], Counter[str], int, list[Caixa]]:
    """Segmenta as caixas no embedding da placa e aplica filtros de qualidade."""
    import cv2

    altura, largura = rgb.shape[:2]
    preditor.set_image(rgb, image_format="RGB")
    cor_fundo = _cor_fundo_lab(rgb)
    uniao = np.zeros((altura, largura), dtype=bool)
    areas_mascaras: list[int] = []
    caixas_aceitas: list[Caixa] = []
    motivos: Counter[str] = Counter()
    processadas = 0

    for caixa in caixas:
        if caixa.area == 0:
            motivos["caixa_vazia"] += 1
            continue
        processadas += 1
        margem = max(3, round(max(caixa.largura, caixa.altura) * 0.4))
        x0 = max(0, caixa.x0 - margem)
        y0 = max(0, caixa.y0 - margem)
        x1 = min(largura, caixa.x1 + margem)
        y1 = min(altura, caixa.y1 + margem)
        segmentar_recorte = getattr(preditor, "segmentar_recorte", None)
        if callable(segmentar_recorte):
            roi, pontuacao = segmentar_recorte(caixa, (x0, y0, x1, y1))
            roi = np.asarray(roi, dtype=np.uint8)
        else:
            box = np.array([caixa.x0, caixa.y0, caixa.x1, caixa.y1], dtype=np.float32)
            mascaras, scores, _ = preditor.predict(box=box, multimask_output=True)
            indice = int(np.argmax(scores))
            prevista = np.asarray(mascaras[indice], dtype=bool)
            pontuacao = float(scores[indice])
            roi = prevista[y0:y1, x0:x1].astype(np.uint8)
            del mascaras, scores, prevista

        quantidade, rotulos, estatisticas, _ = cv2.connectedComponentsWithStats(roi)
        area_original = int(roi.sum())
        if quantidade <= 1 or area_original == 0:
            motivos["sem_componente"] += 1
            continue
        indice_componente = 1 + int(np.argmax(estatisticas[1:, cv2.CC_STAT_AREA]))
        componente = rotulos == indice_componente
        area = int(componente.sum())
        fracao_componente = area / area_original
        area_caixa = max(1, caixa.area)
        contornos, _ = cv2.findContours(
            componente.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
        )
        perimetro = (
            cv2.arcLength(max(contornos, key=cv2.contourArea), True)
            if contornos
            else 0.0
        )
        compacidade = perimetro**2 / (4 * math.pi * area) if area else math.inf

        recorte_rgb = rgb[y0:y1, x0:x1]
        lab = cv2.cvtColor(recorte_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
        distancia = np.linalg.norm(lab - cor_fundo, axis=2)
        escala_distancia = np.clip(distancia * 4, 0, 255).astype(np.uint8)
        limiar_otsu, _ = cv2.threshold(
            escala_distancia, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        mascara_limiar = distancia > max(float(limiar_otsu) / 4.0, 14.0)
        uniao_limiar = np.logical_or(componente, mascara_limiar).sum()
        iou = (
            np.logical_and(componente, mascara_limiar).sum() / uniao_limiar
            if uniao_limiar
            else 0.0
        )
        ys, xs = np.nonzero(componente)
        fora = 1.0 - (
            (
                (xs + x0 >= caixa.x0 - 3)
                & (xs + x0 <= caixa.x1 + 3)
                & (ys + y0 >= caixa.y0 - 3)
                & (ys + y0 <= caixa.y1 + 3)
            ).sum()
            / area
        )
        contraste = float(np.median(distancia[componente])) if area else 0.0
        motivo = None
        if area / area_caixa > 0.95 or area / area_caixa < 0.08:
            motivo = "area_vs_caixa"
        elif fracao_componente < 0.9:
            motivo = "fragmentada"
        elif compacidade > 30:
            motivo = "contorno_picotado"
        elif iou < 0.25:
            motivo = "diverge_do_limiar"
        elif fora > 0.15:
            motivo = "fora_da_caixa"
        elif pontuacao < 0.85:
            motivo = "score_baixo"
        elif contraste < 25:
            motivo = "baixo_contraste"
        if motivo:
            motivos[motivo] += 1
            continue

        x0_placa = max(x0, caixa_placa.x0)
        y0_placa = max(y0, caixa_placa.y0)
        x1_placa = min(x1, caixa_placa.x1)
        y1_placa = min(y1, caixa_placa.y1)
        area_na_placa = int(
            componente[
                y0_placa - y0 : y1_placa - y0,
                x0_placa - x0 : x1_placa - x0,
            ].sum()
        )
        if area_na_placa == 0:
            motivos["fora_da_placa"] += 1
            continue
        areas_mascaras.append(area_na_placa)
        caixas_aceitas.append(caixa)
        uniao[y0:y1, x0:x1] |= componente

    preditor.reset_image()
    return [uniao], areas_mascaras, motivos, processadas, caixas_aceitas


class _SamRecortes:
    """Usa o embedding completo e redimensiona só a região da caixa pedida."""

    def __init__(self, preditor: Any, torch: Any) -> None:
        self.preditor = preditor
        self.torch = torch
        self.funcional = torch.nn.functional

    def set_image(self, imagem: np.ndarray, image_format: str = "RGB") -> None:
        self.preditor.set_image(imagem, image_format=image_format)

    def reset_image(self) -> None:
        self.preditor.reset_image()

    def segmentar_recorte(
        self, caixa: Caixa, recorte: tuple[int, int, int, int]
    ) -> tuple[np.ndarray, float]:
        modelo = self.preditor.model
        x0, y0, x1, y1 = recorte
        altura_original, largura_original = self.preditor.original_size
        with self.torch.inference_mode():
            caixa_tensor = self.torch.tensor(
                [[caixa.x0, caixa.y0, caixa.x1, caixa.y1]],
                dtype=self.torch.float32,
                device=modelo.device,
            )
            caixa_transformada = self.preditor.transform.apply_boxes_torch(
                caixa_tensor, self.preditor.original_size
            )
            esparso, denso = modelo.prompt_encoder(
                points=None, boxes=caixa_transformada, masks=None
            )
            logits, pontuacoes = modelo.mask_decoder(
                image_embeddings=self.preditor.features,
                image_pe=modelo.prompt_encoder.get_dense_pe(),
                sparse_prompt_embeddings=esparso,
                dense_prompt_embeddings=denso,
                multimask_output=True,
            )
            indice = int(self.torch.argmax(pontuacoes[0]).item())
            imagem_logits = self.funcional.interpolate(
                logits[:, indice : indice + 1],
                (modelo.image_encoder.img_size, modelo.image_encoder.img_size),
                mode="bilinear",
                align_corners=False,
            )
            tamanho_entrada_y, tamanho_entrada_x = self.preditor.input_size
            x0_modelo = max(0, round(x0 * tamanho_entrada_x / largura_original))
            y0_modelo = max(0, round(y0 * tamanho_entrada_y / altura_original))
            x1_modelo = min(
                tamanho_entrada_x, round(x1 * tamanho_entrada_x / largura_original)
            )
            y1_modelo = min(
                tamanho_entrada_y, round(y1 * tamanho_entrada_y / altura_original)
            )
            if x1_modelo <= x0_modelo or y1_modelo <= y0_modelo:
                return np.zeros((y1 - y0, x1 - x0), dtype=bool), float(
                    pontuacoes[0, indice].item()
                )
            logits_recorte = imagem_logits[
                :, :, y0_modelo:y1_modelo, x0_modelo:x1_modelo
            ]
            logits_originais = self.funcional.interpolate(
                logits_recorte,
                (y1 - y0, x1 - x0),
                mode="bilinear",
                align_corners=False,
            )[0, 0]
            mascara = (logits_originais > modelo.mask_threshold).cpu().numpy()
            pontuacao = float(pontuacoes[0, indice].item())
        return mascara, pontuacao


def _carregar_sam(caminho_checkpoint: Path) -> Any:
    try:
        import torch
        from segment_anything import SamPredictor, sam_model_registry
    except ImportError as erro:
        raise RuntimeError(
            "SAM é opcional. Instale segment-anything e PyTorch no ambiente de treino."
        ) from erro
    if not caminho_checkpoint.is_file():
        raise FileNotFoundError(f"Checkpoint SAM ausente: {caminho_checkpoint}.")
    dispositivo = "cuda" if torch.cuda.is_available() else "cpu"
    modelo = sam_model_registry["vit_b"](checkpoint=str(caminho_checkpoint))
    modelo.to(device=dispositivo)
    modelo.eval()
    print(f"SAM: vit_b em {dispositivo}", flush=True)
    return _SamRecortes(SamPredictor(modelo), torch)


def criar_dataset_real(
    fonte: Path = FONTE_PADRAO,
    saida: Path = SAIDA_PADRAO,
    checkpoint: Path = CHECKPOINT_PADRAO,
    escala_leitura: float = ESCALA_ENTRADA_PADRAO,
    limite_cartoes: int | None = None,
    preditor: Any | None = None,
) -> dict[str, Any]:
    """Gera imagens e máscaras estimadas para avaliação do conjunto real UMS."""
    if escala_leitura not in (0.25, 0.5):
        raise ValueError("A escala de leitura aceita somente 0.25 ou 0.5.")
    fonte = fonte.resolve()
    saida = saida.resolve()
    if not fonte.is_dir():
        raise FileNotFoundError(f"Diretório de cartões UMS ausente: {fonte}.")
    if saida.exists() and any(saida.iterdir()):
        raise ValueError(f"A saída precisa ser nova ou vazia: {saida}.")
    cartoes = _carregar_cartoes(fonte)
    if limite_cartoes is not None:
        if limite_cartoes < 1:
            raise ValueError("--limite-cartoes precisa ser positivo.")
        cartoes = cartoes[:limite_cartoes]
    if preditor is None:
        preditor = _carregar_sam(checkpoint)

    imagens_saida = saida / "imagens"
    mascaras_saida = saida / "mascaras"
    imagens_saida.mkdir(parents=True, exist_ok=True)
    mascaras_saida.mkdir(parents=True, exist_ok=True)
    registros: list[dict[str, Any]] = []
    rejeicoes_totais: Counter[str] = Counter()
    area_caixas_total = 0
    area_mascaras_total = 0
    anotacoes_totais = 0
    mascaras_aceitas = 0
    caixas_aceitas_total = 0

    for numero, cartao in enumerate(cartoes, start=1):
        imagem_reduzida = _abrir_reduzida(cartao.caminho, escala_leitura)
        largura_reduzida, altura_reduzida = imagem_reduzida.size
        rgb = np.asarray(imagem_reduzida, dtype=np.uint8)
        caixas = [
            _recortar_caixa(
                tuple(float(valor) for valor in anotacao["bbox"]),
                cartao.largura,
                cartao.altura,
                (
                    round(cartao.largura * escala_leitura),
                    round(cartao.altura * escala_leitura),
                ),
            )
            for anotacao in cartao.anotacoes
        ]
        # O backend JPEG pode arredondar a largura draft em um pixel.
        fator_x = largura_reduzida / max(1, round(cartao.altura * escala_leitura))
        fator_y = altura_reduzida / max(1, round(cartao.largura * escala_leitura))
        if abs(fator_x - fator_y) > 0.01:
            caixas = [
                Caixa(
                    round(caixa.x0 * fator_x),
                    round(caixa.y0 * fator_y),
                    round(caixa.x1 * fator_x),
                    round(caixa.y1 * fator_y),
                )
                for caixa in caixas
            ]
        caixa_placa = _detectar_caixa_placa(rgb, caixas)
        (
            unioes,
            areas_mascaras,
            motivos,
            processadas,
            caixas_aceitas,
        ) = _segmentar_anotacoes(rgb, caixas, caixa_placa, preditor)
        mascara_classes = _criar_mascara_classes(
            (largura_reduzida, altura_reduzida), caixa_placa, unioes
        )
        imagem_final, mascara_final, fator_saida = _preparar_saida(
            imagem_reduzida, mascara_classes
        )
        cobertura = _percentual_cobertura(np.asarray(mascara_final, dtype=np.uint8))
        imagem_final.save(imagens_saida / f"{cartao.nome}.png", format="PNG")
        mascara_final.save(mascaras_saida / f"{cartao.nome}.png", format="PNG")

        caixas_na_placa = [
            Caixa(
                max(caixa.x0, caixa_placa.x0) - caixa_placa.x0,
                max(caixa.y0, caixa_placa.y0) - caixa_placa.y0,
                min(caixa.x1, caixa_placa.x1) - caixa_placa.x0,
                min(caixa.y1, caixa_placa.y1) - caixa_placa.y0,
            )
            for caixa in caixas_aceitas
        ]
        resumo = _resumo_areas(caixas_na_placa, areas_mascaras)
        area_caixas_total += int(resumo["soma_area_caixas_px"])
        area_mascaras_total += int(resumo["soma_area_mascaras_px"])
        anotacoes_totais += len(cartao.anotacoes)
        mascaras_aceitas += len(areas_mascaras)
        caixas_aceitas_total += len(caixas_aceitas)
        rejeicoes_totais.update(motivos)
        hash_nome = hashlib.sha256(cartao.nome.encode("utf-8")).digest()
        semente = (int.from_bytes(hash_nome[:4], "big") & 0x7FFFFFFF) ^ SEMENTE_GLOBAL
        registros.append(
            {
                "id": cartao.nome,
                "semente": semente,
                "conjunto": "teste",
                "faixa_cobertura_alvo": _faixa_status(cobertura),
                "percentual_cobertura_alvo": cobertura,
                "percentual_cobertura_real": cobertura,
                "alvo_atingido": None,
                "idade_simulada_dias": 0.0,
                "idade_conhecida": False,
                "n_sprites": len(areas_mascaras),
                "distratores_presentes": [],
                "dominante_cor": "real_ums",
                "pesos_grupo": {},
                "px_por_mm": PX_POR_MM_FONTE * escala_leitura * fator_saida,
                "k_escala": 1.0,
                "origem": "real",
                "mascara": "estimada_por_sam",
                "anotacoes_coco": len(cartao.anotacoes),
                "mascaras_sam_aceitas": len(areas_mascaras),
                "caixa_placa": {
                    "x0": caixa_placa.x0,
                    "y0": caixa_placa.y0,
                    "x1": caixa_placa.x1,
                    "y1": caixa_placa.y1,
                },
                "soma_area_caixas_px": resumo["soma_area_caixas_px"],
                "soma_area_mascaras_px": resumo["soma_area_mascaras_px"],
                "diferenca_relativa_caixa_percentual": resumo[
                    "diferenca_relativa_percentual"
                ],
                "rejeicoes_segmentacao": dict(motivos),
                "anotacoes_processadas": processadas,
            }
        )
        print(
            f"{numero}/{len(cartoes)} {cartao.nome}: {cobertura:.2f}% "
            f"({len(areas_mascaras)}/{len(cartao.anotacoes)} segmentos)",
            flush=True,
        )
        del rgb, mascara_classes, imagem_reduzida, imagem_final, mascara_final

    diferenca_total = area_mascaras_total - area_caixas_total
    relatorio = {
        "origem": "real",
        "mascara": "estimada_por_sam",
        "fonte": "Ong & Lim (2025), CC BY 4.0, DOI 10.6084/m9.figshare.28280792.v1",
        "semente_global": SEMENTE_GLOBAL,
        "escala_leitura": escala_leitura,
        "px_por_mm_fonte": PX_POR_MM_FONTE,
        "tamanho_saida": [LARGURA_SAIDA, ALTURA_SAIDA],
        "cartoes": len(registros),
        "anotacoes_coco": anotacoes_totais,
        "caixas_sam_aceitas": caixas_aceitas_total,
        "mascaras_sam_aceitas": mascaras_aceitas,
        "taxa_aceitacao_segmentacao_percentual": (
            mascaras_aceitas * 100.0 / anotacoes_totais if anotacoes_totais else 0.0
        ),
        "soma_area_caixas_px": area_caixas_total,
        "soma_area_mascaras_px": area_mascaras_total,
        "diferenca_area_px": diferenca_total,
        "diferenca_relativa_percentual": (
            diferenca_total * 100.0 / area_caixas_total if area_caixas_total else 0.0
        ),
        "rejeicoes": dict(rejeicoes_totais),
        "interpretacao": (
            "A diferença compara, para os mesmos objetos aceitos pelos filtros, "
            "a área da máscara SAM com a área da caixa COCO. A caixa é uma "
            "aproximação retangular e essa diferença não mede erro contra uma "
            "máscara manual independente."
        ),
    }
    (saida / "metadados.jsonl").write_text(
        "".join(
            json.dumps(registro, ensure_ascii=False, sort_keys=True) + "\n"
            for registro in registros
        ),
        encoding="utf-8",
    )
    configuracao = {
        "semente_global": SEMENTE_GLOBAL,
        "origem": "real",
        "mascara": "estimada_por_sam",
        "fonte_dados": str(fonte),
        "checkpoint_sam": str(checkpoint),
        "escala_leitura": escala_leitura,
        "divisao": {"treino": 0, "validacao": 0, "teste": 1},
        "resolucao": [LARGURA_SAIDA, ALTURA_SAIDA],
        "valores_mascara": VALORES_CLASSES,
        "versao_gerador": 1,
    }
    (saida / "configuracao.json").write_text(
        json.dumps(configuracao, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    (saida / "relatorio_estimativa.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return relatorio


def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Monta avaliação real UMS com máscaras estimadas por SAM."
    )
    parser.add_argument("--fonte", type=Path, default=FONTE_PADRAO)
    parser.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    parser.add_argument("--checkpoint", type=Path, default=CHECKPOINT_PADRAO)
    parser.add_argument(
        "--escala-leitura",
        type=float,
        choices=(0.25, 0.5),
        default=ESCALA_ENTRADA_PADRAO,
        help="Fração da resolução JPEG decodificada para caber na memória.",
    )
    parser.add_argument(
        "--limite-cartoes",
        type=int,
        help="Limita cartões para uma execução de conferência.",
    )
    return parser


def main(argumentos: list[str] | None = None) -> int:
    parser = criar_parser()
    opcoes = parser.parse_args(argumentos)
    try:
        relatorio = criar_dataset_real(
            fonte=opcoes.fonte,
            saida=opcoes.saida,
            checkpoint=opcoes.checkpoint,
            escala_leitura=opcoes.escala_leitura,
            limite_cartoes=opcoes.limite_cartoes,
        )
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as erro:
        parser.error(str(erro))
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
