"""Segmenta caixas COCO nos originais e projeta máscaras para a resolução do modelo.

As caixas humanas localizam recortes de 256 a 1024 pixels. O QC usa área,
componente principal e cobertura da caixa; propostas reprovadas viram 255.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np
from PIL import Image

from training.revisar_originais_ums import Transformacao
from training.teste_real_ums import (
    _abrir_reduzida,
    _carregar_cartoes,
    _carregar_sam,
    _preparar_saida,
)

LARGURA = 768
ALTURA = 576
MARGEM_MINIMA = 64
FATOR_MARGEM = 0.20
TAMANHO_CELULA = 192
TAMANHO_MINIMO_RECORTE = 256
TAMANHO_MAXIMO_RECORTE = 1024
LOTE_PREDICAO = 8
VERSAO = "segmentacao_coco_originais_v5_sem_recorte_placa"


@dataclass(frozen=True)
class Janela:
    """Recorte nativo que contém um grupo de caixas humanas."""

    xyxy: tuple[int, int, int, int]
    anotacoes: tuple[dict[str, Any], ...]


def hash_arquivo(caminho: Path) -> str:
    """Calcula SHA-256 em blocos para não carregar originais inteiros na RAM."""
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _id_ordenavel(anotacao: dict[str, Any]) -> tuple[int, str]:
    valor = anotacao.get("id", "")
    if isinstance(valor, int):
        return (0, f"{valor:020d}")
    return (1, str(valor))


def _margem(anotacao: dict[str, Any]) -> int:
    _, _, largura, altura = anotacao["bbox"]
    return max(MARGEM_MINIMA, round(max(largura, altura) * FATOR_MARGEM))


def _envelope(anotacoes: Iterable[dict[str, Any]]) -> tuple[float, float, float, float]:
    x0s, y0s, x1s, y1s = [], [], [], []
    for anotacao in anotacoes:
        x, y, largura, altura = anotacao["bbox"]
        margem = _margem(anotacao)
        x0s.append(x - margem)
        y0s.append(y - margem)
        x1s.append(x + largura + margem)
        y1s.append(y + altura + margem)
    return min(x0s), min(y0s), max(x1s), max(y1s)


def agrupar_caixas(
    anotacoes: Iterable[dict[str, Any]], largura: int, altura: int
) -> list[Janela]:
    """Agrupa caixas próximas sem exceder os limites de tamanho do SAM."""
    celulas: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    grandes: list[dict[str, Any]] = []
    for anotacao in anotacoes:
        x, y, w, h = anotacao["bbox"]
        if w <= 0 or h <= 0:
            raise ValueError(f"Caixa COCO inválida: {anotacao.get('id')}.")
        if max(w, h) + 2 * _margem(anotacao) > TAMANHO_MAXIMO_RECORTE:
            grandes.append(anotacao)
            continue
        cx, cy = x + w / 2, y + h / 2
        celulas[(int(cx // TAMANHO_CELULA), int(cy // TAMANHO_CELULA))].append(anotacao)

    grupos: list[list[dict[str, Any]]] = [
        sorted(grupo, key=_id_ordenavel) for grupo in celulas.values()
    ]
    grupos.extend([[anotacao] for anotacao in grandes])
    pendentes = list(grupos)
    grupos_validos: list[list[dict[str, Any]]] = []
    while pendentes:
        grupo = pendentes.pop()
        x0, y0, x1, y1 = _envelope(grupo)
        if max(x1 - x0, y1 - y0) <= TAMANHO_MAXIMO_RECORTE or len(grupo) == 1:
            grupos_validos.append(grupo)
            continue
        eixo_x = x1 - x0 >= y1 - y0
        ordenado = sorted(
            grupo,
            key=lambda a: (
                a["bbox"][0] + a["bbox"][2] / 2
                if eixo_x
                else a["bbox"][1] + a["bbox"][3] / 2
            ),
        )
        meio = len(ordenado) // 2
        pendentes.extend((ordenado[:meio], ordenado[meio:]))

    janelas = []
    for grupo in grupos_validos:
        x0, y0, x1, y1 = _envelope(grupo)
        lado = min(
            TAMANHO_MAXIMO_RECORTE,
            max(TAMANHO_MINIMO_RECORTE, math.ceil(max(x1 - x0, y1 - y0))),
        )
        centro_x, centro_y = (x0 + x1) / 2, (y0 + y1) / 2
        ix0 = min(max(0, round(centro_x - lado / 2)), max(0, largura - lado))
        iy0 = min(max(0, round(centro_y - lado / 2)), max(0, altura - lado))
        ix1, iy1 = min(largura, ix0 + lado), min(altura, iy0 + lado)
        janelas.append(
            Janela((ix0, iy0, ix1, iy1), tuple(sorted(grupo, key=_id_ordenavel)))
        )
    return sorted(
        janelas, key=lambda j: (j.xyxy[1], j.xyxy[0], _id_ordenavel(j.anotacoes[0]))
    )


def componente_principal(mascara: np.ndarray) -> np.ndarray:
    """Retorna apenas o maior componente 8-conexo da proposta SAM."""
    n, rotulos, stats, _ = cv2.connectedComponentsWithStats(
        mascara.astype(np.uint8), connectivity=8
    )
    if n <= 1:
        return np.zeros(mascara.shape, dtype=bool)
    indice = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return rotulos == indice


def medir_qc(
    mascara: np.ndarray, caixa_xyxy: tuple[int, int, int, int], score: float
) -> dict[str, Any]:
    """Avalia área, componente e cobertura da caixa, sem usar cor ou brilho."""
    x0, y0, x1, y1 = caixa_xyxy
    area_caixa = max(1, (x1 - x0) * (y1 - y0))
    componente = componente_principal(mascara)
    area = int(componente.sum())
    ys, xs = np.where(componente)
    if not len(xs):
        cobertura_caixa = 0.0
    else:
        bx0, bx1 = int(xs.min()), int(xs.max()) + 1
        by0, by1 = int(ys.min()), int(ys.max()) + 1
        intersecao = max(0, min(x1, bx1) - max(x0, bx0)) * max(
            0, min(y1, by1) - max(y0, by0)
        )
        cobertura_caixa = intersecao / area_caixa
    razao_area = area / area_caixa
    motivos = []
    if area == 0:
        motivos.append("sem_componente")
    if razao_area < 0.25:
        motivos.append("area_menor_que_25_porcento_da_caixa")
    if razao_area > 1.0:
        motivos.append("area_maior_que_a_caixa")
    if cobertura_caixa < 0.60:
        motivos.append("caixa_da_mascara_cobre_menos_de_60_porcento")
    return {
        "mascara": componente,
        "score_sam": float(score),
        "area_componente_px": area,
        "razao_area_caixa": float(razao_area),
        "cobertura_bbox_coco": float(cobertura_caixa),
        "aprovada": not motivos,
        "motivos": motivos,
    }


def selecionar_proposta(
    mascaras: np.ndarray, scores: np.ndarray, caixa_xyxy: tuple[int, int, int, int]
) -> dict[str, Any]:
    """Escolhe a máscara de maior score entre as que passam o QC fixado."""
    medidas = [
        medir_qc(m, caixa_xyxy, float(s)) for m, s in zip(mascaras, scores, strict=True)
    ]
    elegiveis = [m for m in medidas if m["aprovada"]]
    escolhida = max(elegiveis or medidas, key=lambda m: m["score_sam"])
    escolhida["candidatas_qc"] = [
        {k: v for k, v in medida.items() if k != "mascara"} for medida in medidas
    ]
    return escolhida


def _projetar_mascara(
    mascara: np.ndarray,
    janela: tuple[int, int, int, int],
    transformacao: Transformacao,
) -> tuple[np.ndarray, float, int]:
    """Reduz por área após rotação e mantém o número de pixels esperado."""
    x0, y0, x1, y1 = janela
    sx = transformacao.largura_conteudo / transformacao.altura
    sy = transformacao.altura_conteudo / transformacao.largura
    esperado = float(mascara.sum()) * sx * sy
    largura_saida = max(1, round((y1 - y0) * sx))
    altura_saida = max(1, round((x1 - x0) * sy))
    imagem = Image.fromarray(mascara.astype(np.uint8) * 255)
    reduzida = imagem.transpose(Image.Transpose.ROTATE_90).resize(
        (largura_saida, altura_saida), Image.Resampling.BOX
    )
    fracao = np.asarray(reduzida, dtype=np.uint8).ravel()
    quantidade = min(len(fracao), max(1, round(esperado))) if mascara.any() else 0
    projetada = np.zeros(len(fracao), dtype=bool)
    if quantidade:
        candidatos = np.flatnonzero(fracao)
        if len(candidatos) < quantidade:
            ordem = np.argsort(-fracao.astype(np.int16), kind="stable")[:quantidade]
        else:
            ordem_local = np.argsort(-fracao[candidatos], kind="stable")[:quantidade]
            ordem = candidatos[ordem_local]
        projetada[ordem] = True
    patch = projetada.reshape(altura_saida, largura_saida)
    inicio_x = transformacao.offset_x + round(y0 * sx)
    inicio_y = transformacao.offset_y + round((transformacao.largura - x1) * sy)
    completa = np.zeros((ALTURA, LARGURA), dtype=bool)
    px0, py0 = max(0, inicio_x), max(0, inicio_y)
    px1, py1 = (
        min(LARGURA, inicio_x + largura_saida),
        min(ALTURA, inicio_y + altura_saida),
    )
    if px1 > px0 and py1 > py0:
        completa[py0:py1, px0:px1] = patch[
            py0 - inicio_y : py1 - inicio_y, px0 - inicio_x : px1 - inicio_x
        ]
    imagem.close()
    reduzida.close()
    return completa, esperado, int(completa.sum())


def _transformar_bbox(
    bbox: list[float], transformacao: Transformacao
) -> tuple[int, int, int, int]:
    x, y, largura, altura = bbox
    p0 = transformacao.direto(x, y)
    p1 = transformacao.direto(x + largura, y + altura)
    return (
        max(0, math.floor(min(p0[0], p1[0]))),
        max(0, math.floor(min(p0[1], p1[1]))),
        min(LARGURA, math.ceil(max(p0[0], p1[0]))),
        min(ALTURA, math.ceil(max(p0[1], p1[1]))),
    )


def _transformacao(cartao: Any, imagem_reduzida: Path) -> Transformacao:
    limite_anterior = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None
    try:
        pequena = _abrir_reduzida(cartao.caminho, 0.25)
    finally:
        Image.MAX_IMAGE_PIXELS = limite_anterior
    fator = min(LARGURA / pequena.width, ALTURA / pequena.height)
    nw, nh = round(pequena.width * fator), round(pequena.height * fator)
    transformacao = Transformacao(
        cartao.largura,
        cartao.altura,
        nw,
        nh,
        (LARGURA - nw) // 2,
        (ALTURA - nh) // 2,
    )
    recriada, _, _ = _preparar_saida(
        pequena, np.zeros((pequena.height, pequena.width), dtype=np.uint8)
    )
    referencia = Image.open(imagem_reduzida).convert("RGB")
    if not np.array_equal(np.asarray(recriada), np.asarray(referencia)):
        raise ValueError(f"A transformação não reproduz {cartao.nome}.")
    referencia.close()
    recriada.close()
    pequena.close()
    return transformacao


def _caixa_local(
    anotacao: dict[str, Any], janela: tuple[int, int, int, int]
) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = janela
    x, y, largura, altura = anotacao["bbox"]
    return (
        max(0, round(x - x0)),
        max(0, round(y - y0)),
        min(x1 - x0, round(x + largura - x0)),
        min(y1 - y0, round(y + altura - y0)),
    )


def medir_desvio_mapeamento(
    anotacoes: list[dict[str, Any]], transformacao: Transformacao
) -> dict[str, Any]:
    """Verifica o ciclo original → saída → original em caixas COCO humanas."""
    selecionadas = sorted(
        anotacoes,
        key=lambda a: (a["bbox"][2] * a["bbox"][3], _id_ordenavel(a)),
    )
    if len(selecionadas) > 5:
        indices = sorted(
            {
                0,
                len(selecionadas) // 4,
                len(selecionadas) // 2,
                3 * len(selecionadas) // 4,
                len(selecionadas) - 1,
            }
        )
        selecionadas = [selecionadas[i] for i in indices]
    desvios = []
    for anotacao in selecionadas:
        x, y, largura, altura = anotacao["bbox"]
        for px, py in (
            (x, y),
            (x + largura, y),
            (x, y + altura),
            (x + largura, y + altura),
        ):
            original = (px, py)
            reconstituida = transformacao.inverso(*transformacao.direto(*original))
            desvios.append(math.dist(original, reconstituida))
    return {
        "caixas_coco_verificadas": len(selecionadas),
        "pontos_verificados": len(desvios),
        "desvio_maximo_original_px": max(desvios, default=0.0),
        "limite_px": 1.0,
        "aprovado": max(desvios, default=0.0) <= 1.0,
    }


def _propor_mascaras(
    predictor: Any,
    torch: Any,
    crop: np.ndarray,
    janela: Janela,
) -> list[dict[str, Any]]:
    """Executa caixas em lotes sobre um embedding nativo compartilhado."""
    predictor.set_image(crop, image_format="RGB")
    propostas = []
    x0, y0, _, _ = janela.xyxy
    with torch.inference_mode():
        for inicio in range(0, len(janela.anotacoes), LOTE_PREDICAO):
            anotacoes = janela.anotacoes[inicio : inicio + LOTE_PREDICAO]
            caixas = np.asarray(
                [
                    [
                        max(0, a["bbox"][0] - x0),
                        max(0, a["bbox"][1] - y0),
                        min(crop.shape[1], a["bbox"][0] + a["bbox"][2] - x0),
                        min(crop.shape[0], a["bbox"][1] + a["bbox"][3] - y0),
                    ]
                    for a in anotacoes
                ],
                dtype=np.float32,
            )
            caixas_torch = torch.as_tensor(
                caixas, dtype=torch.float32, device=predictor.device
            )
            caixas_transformadas = predictor.transform.apply_boxes_torch(
                caixas_torch, predictor.original_size
            )
            mascaras, scores, _ = predictor.predict_torch(
                point_coords=None,
                point_labels=None,
                boxes=caixas_transformadas,
                multimask_output=True,
                return_logits=False,
            )
            mascaras_cpu = mascaras.cpu().numpy()
            scores_cpu = scores.cpu().numpy()
            for anotacao, caixa, opcoes, pontuacoes in zip(
                anotacoes, caixas, mascaras_cpu, scores_cpu, strict=True
            ):
                selecionada = selecionar_proposta(
                    opcoes,
                    pontuacoes,
                    tuple(int(round(v)) for v in caixa),
                )
                selecionada["anotacao"] = anotacao
                selecionada["caixa_local_xyxy"] = [int(round(v)) for v in caixa]
                propostas.append(selecionada)
            del mascaras, scores, caixas_torch, caixas_transformadas
    predictor.reset_image()
    return propostas


def _salvar_recorte(
    imagem_reduzida: np.ndarray,
    mascara: np.ndarray,
    destino: Path,
) -> None:
    """Grava recorte RGBA na escala do modelo, preservando cores da fonte."""
    ys, xs = np.where(mascara)
    if not len(xs):
        return
    x0, x1 = max(0, int(xs.min()) - 2), min(LARGURA, int(xs.max()) + 3)
    y0, y1 = max(0, int(ys.min()) - 2), min(ALTURA, int(ys.max()) + 3)
    rgba = np.dstack(
        (imagem_reduzida[y0:y1, x0:x1], mascara[y0:y1, x0:x1].astype(np.uint8) * 255)
    )
    destino.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, "RGBA").save(destino, format="PNG", optimize=True)


def _rasterizar_caixa(bbox: list[float], transformacao: Transformacao) -> np.ndarray:
    x0, y0, x1, y1 = _transformar_bbox(bbox, transformacao)
    mascara = np.zeros((ALTURA, LARGURA), dtype=bool)
    if x1 > x0 and y1 > y0:
        mascara[y0:y1, x0:x1] = True
    return mascara


def processar_placa(
    cartao: Any,
    origem_reduzida: Path,
    saida: Path,
    recortes_saida: Path,
    transformacao: Transformacao,
    predictor: Any,
    torch: Any,
    checkpoint_sha256: str,
    anotacoes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Segmenta uma placa e salva máscara, recortes e métricas recuperáveis."""
    imagem_path = origem_reduzida / "imagens" / f"{cartao.nome}.png"
    mascara_path = origem_reduzida / "mascaras" / f"{cartao.nome}.png"
    imagem = np.asarray(Image.open(imagem_path).convert("RGB"))
    mascara_origem = np.asarray(Image.open(mascara_path).convert("L"), dtype=np.uint8)
    if imagem.shape[:2] != (ALTURA, LARGURA) or mascara_origem.shape != (
        ALTURA,
        LARGURA,
    ):
        raise ValueError(f"Resolução inesperada em {cartao.nome}.")
    placa = mascara_origem > 0
    mascara_final = mascara_origem.copy()
    mascara_final[mascara_final == 2] = 1
    mascara_aceita = np.zeros((ALTURA, LARGURA), dtype=bool)
    mascara_ignorada = np.zeros((ALTURA, LARGURA), dtype=bool)
    registro_anotacoes = []
    anotacoes = list(cartao.anotacoes if anotacoes is None else anotacoes)
    janelas = agrupar_caixas(anotacoes, cartao.largura, cartao.altura)
    limite_anterior = Image.MAX_IMAGE_PIXELS
    try:
        Image.MAX_IMAGE_PIXELS = None
        with Image.open(cartao.caminho) as original:
            if original.size != (cartao.largura, cartao.altura):
                raise ValueError(f"Dimensões do original divergentes: {cartao.nome}.")
            original.load()
            for janela in janelas:
                crop_img = original.crop(janela.xyxy).convert("RGB")
                crop = np.asarray(crop_img, dtype=np.uint8)
                propostas = _propor_mascaras(predictor, torch, crop, janela)
                for proposta in propostas:
                    anotacao = proposta["anotacao"]
                    caixa_modelo = _transformar_bbox(anotacao["bbox"], transformacao)
                    local = _caixa_local(anotacao, janela.xyxy)
                    x, y, largura, altura = anotacao["bbox"]
                    caixa_truncada = local[2] - local[0] < round(x + largura) - round(
                        x
                    ) or local[3] - local[1] < round(y + altura) - round(y)
                    if caixa_truncada:
                        proposta["aprovada"] = False
                        proposta["motivos"].append("caixa_excede_recorte_maximo")
                    if proposta["aprovada"]:
                        projetada, area_esperada, area_projetada = _projetar_mascara(
                            proposta["mascara"], janela.xyxy, transformacao
                        )
                        mascara_aceita |= projetada
                        nome_recorte = f"{int(anotacao['id']):08d}.png"
                        _salvar_recorte(
                            imagem,
                            projetada,
                            recortes_saida / cartao.nome / nome_recorte,
                        )
                    else:
                        projetada = np.zeros_like(placa)
                        area_esperada = 0.0
                        area_projetada = 0
                    if not proposta["aprovada"]:
                        mascara_ignorada |= _rasterizar_caixa(
                            anotacao["bbox"], transformacao
                        )
                    registro_anotacoes.append(
                        {
                            "id": anotacao["id"],
                            "taxon": anotacao.get("taxon"),
                            "bbox_original_xywh": [float(v) for v in anotacao["bbox"]],
                            "bbox_modelo_xyxy": list(caixa_modelo),
                            "aprovada": bool(proposta["aprovada"]),
                            "score_sam": proposta["score_sam"],
                            "area_componente_original_px": proposta[
                                "area_componente_px"
                            ],
                            "razao_area_caixa": proposta["razao_area_caixa"],
                            "cobertura_bbox_coco": proposta["cobertura_bbox_coco"],
                            "area_projetada_esperada_px": area_esperada,
                            "area_projetada_real_px": area_projetada,
                            "erro_projecao_relativo": (
                                abs(area_projetada - area_esperada) / area_esperada
                                if area_esperada
                                else 0.0
                            ),
                            "motivos_reprovacao": proposta["motivos"],
                            "candidatas_qc": proposta["candidatas_qc"],
                        }
                    )
                crop_img.close()
                del crop, propostas
            original_hash = hash_arquivo(cartao.caminho)
    finally:
        Image.MAX_IMAGE_PIXELS = limite_anterior
    mascara_final[mascara_ignorada & ~mascara_aceita & placa] = 255
    mascara_final[mascara_aceita] = 2
    mascara_destino = saida / "mascaras" / f"{cartao.nome}.png"
    mascara_destino.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(mascara_final, "L").save(
        mascara_destino, format="PNG", optimize=True
    )
    aceitas = sum(item["aprovada"] for item in registro_anotacoes)
    registro = {
        "versao": VERSAO,
        "checkpoint_sha256": checkpoint_sha256,
        "placa": cartao.nome,
        "sha256_original": original_hash,
        "sha256_mascara_origem": hash_arquivo(mascara_path),
        "transformacao": transformacao.__dict__,
        "validacao_mapeamento": medir_desvio_mapeamento(anotacoes, transformacao),
        "caixas_coco": len(registro_anotacoes),
        "mascaras_aprovadas": aceitas,
        "mascaras_reprovadas": len(registro_anotacoes) - aceitas,
        "taxa_aprovacao": aceitas / max(1, len(registro_anotacoes)),
        "area_insetos_modelo_px": int(mascara_aceita.sum()),
        "pixels_ignorados": int(np.count_nonzero(mascara_final == 255)),
        "area_projetada_esperada_soma_px": float(
            sum(item["area_projetada_esperada_px"] for item in registro_anotacoes)
        ),
        "area_projetada_soma_px": int(
            sum(item["area_projetada_real_px"] for item in registro_anotacoes)
        ),
        "erro_projecao_agregado": 0.0,
        "anotacoes": registro_anotacoes,
    }
    esperado = registro["area_projetada_esperada_soma_px"]
    registro["erro_projecao_agregado"] = (
        abs(registro["area_projetada_soma_px"] - esperado) / esperado
        if esperado
        else 0.0
    )
    arquivo_registro = saida / "registros" / f"{cartao.nome}.json"
    arquivo_registro.parent.mkdir(parents=True, exist_ok=True)
    arquivo_registro.write_text(
        json.dumps(registro, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    catalogo = recortes_saida / "catalogos" / f"{cartao.nome}.jsonl"
    catalogo.parent.mkdir(parents=True, exist_ok=True)
    catalogo.write_text(
        "".join(
            json.dumps(
                {
                    "placa_origem": cartao.nome,
                    "anotacao_coco_id": item["id"],
                    "taxon": item["taxon"],
                    "aprovada": item["aprovada"],
                    "arquivo": f"{cartao.nome}/{int(item['id']):08d}.png"
                    if item["aprovada"] and item["area_projetada_real_px"]
                    else None,
                    "area_projetada_px": item["area_projetada_real_px"],
                    "sha256_original": original_hash,
                    "revisao": VERSAO,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n"
            for item in registro_anotacoes
        ),
        encoding="utf-8",
    )
    return registro


def _dentro_de(arquivo: Path, raiz: Path) -> bool:
    """Confirma que o caminho temporário pertence à pasta de recortes desta execução."""
    arquivo_resolvido = arquivo.resolve()
    raiz_resolvida = raiz.resolve()
    return arquivo_resolvido != raiz_resolvida and arquivo_resolvido.is_relative_to(
        raiz_resolvida
    )


def conservar_recortes_de_composicao(
    biblioteca: Path,
    placas_composicao: set[str],
    placas_avaliacao: set[str],
) -> dict[str, Any]:
    """Remove apenas recortes das placas reservadas à avaliação."""
    raiz = biblioteca.resolve()
    catalogos = raiz / "catalogos"
    if placas_composicao & placas_avaliacao:
        raise ValueError("Composição e avaliação não podem compartilhar placas.")
    esperadas = placas_composicao | placas_avaliacao
    if not catalogos.is_dir():
        raise FileNotFoundError(f"Catálogos de recortes ausentes: {catalogos}.")
    desconhecidos = [
        caminho.name
        for caminho in raiz.iterdir()
        if caminho.name not in {"catalogos", "configuracao.json", ".staging"}
        and caminho.name not in esperadas
    ]
    if desconhecidos:
        raise FileExistsError(
            "A biblioteca contém pastas sem placa reconhecida: "
            + ", ".join(sorted(desconhecidos)[:5])
        )
    desconhecidos_catalogos = [
        caminho.stem
        for caminho in catalogos.glob("*.jsonl")
        if caminho.stem not in esperadas
    ]
    if desconhecidos_catalogos:
        raise FileExistsError(
            "A biblioteca contém catálogos sem placa reconhecida: "
            + ", ".join(sorted(desconhecidos_catalogos)[:5])
        )

    recortes_removidos = 0
    catalogos_removidos = 0
    for nome in sorted(placas_avaliacao):
        pasta = raiz / nome
        if pasta.exists():
            if not _dentro_de(pasta, raiz) or not pasta.is_dir():
                raise ValueError(f"Pasta de recortes fora da biblioteca: {pasta}.")
            recortes_removidos += sum(
                1 for item in pasta.rglob("*.png") if item.is_file()
            )
            shutil.rmtree(pasta)
        catalogo = catalogos / f"{nome}.jsonl"
        if catalogo.exists():
            if not _dentro_de(catalogo, raiz) or not catalogo.is_file():
                raise ValueError(f"Catálogo fora da biblioteca: {catalogo}.")
            catalogo.unlink()
            catalogos_removidos += 1

    caminho_configuracao = raiz / "configuracao.json"
    configuracao = json.loads(caminho_configuracao.read_text("utf-8"))
    por_placa = configuracao.get("recortes_por_placa", {})
    configuracao["recortes_por_placa"] = {
        nome: por_placa[nome] for nome in sorted(placas_composicao) if nome in por_placa
    }
    configuracao["placas_composicao"] = sorted(placas_composicao)
    configuracao["placas_avaliacao_excluidas"] = sorted(placas_avaliacao)
    configuracao["politica_avaliacao"] = (
        "Imagens e máscaras ficam na pasta de máscaras; recortes e catálogos de placas "
        "reservadas foram removidos da biblioteca de composição."
    )
    temporario = caminho_configuracao.with_suffix(".json.part")
    temporario.write_text(
        json.dumps(configuracao, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporario.replace(caminho_configuracao)
    return {
        "placas_composicao": len(placas_composicao),
        "placas_avaliacao_excluidas": len(placas_avaliacao),
        "catalogos_avaliacao_removidos": catalogos_removidos,
        "recortes_avaliacao_removidos": recortes_removidos,
    }


def _placa_completa(
    cartao: Any,
    saida: Path,
    recortes_saida: Path,
    reduzidas: Path,
    checkpoint_sha256: str,
) -> dict[str, Any] | None:
    """Reaproveita uma placa finalizada apenas se hashes e recortes conferirem."""
    caminho_registro = saida / "registros" / f"{cartao.nome}.json"
    caminho_mascara = saida / "mascaras" / f"{cartao.nome}.png"
    if not caminho_registro.is_file() or not caminho_mascara.is_file():
        return None
    registro = json.loads(caminho_registro.read_text("utf-8"))
    if (
        registro.get("versao") != VERSAO
        or registro.get("sha256_original") != hash_arquivo(cartao.caminho)
        or registro.get("sha256_mascara_origem")
        != hash_arquivo(reduzidas / "mascaras" / f"{cartao.nome}.png")
        or registro.get("checkpoint_sha256") != checkpoint_sha256
    ):
        return None
    if not (recortes_saida / "catalogos" / f"{cartao.nome}.jsonl").is_file():
        return None
    arquivos = [
        recortes_saida / cartao.nome / f"{int(item['id']):08d}.png"
        for item in registro.get("anotacoes", [])
        if item.get("aprovada") and item.get("area_projetada_real_px", 0) > 0
    ]
    if any(not caminho.is_file() for caminho in arquivos):
        return None
    return registro


def _carregar_tons(cartao: Any) -> dict[int, str]:
    documento = json.loads(
        (cartao.caminho.parent / "instances_default.json").read_text("utf-8")
    )
    return {categoria["id"]: categoria["name"] for categoria in documento["categories"]}


def executar(
    originais: Path,
    reduzidas: Path,
    saida: Path,
    recortes_saida: Path,
    checkpoint: Path,
    limite_anotacoes: int | None = None,
    limite_placas: int | None = None,
    somente_placa: str | None = None,
) -> dict[str, Any]:
    """Executa o pipeline com estado por placa para permitir retomada."""
    permitidos = {"auditoria", "mascaras", "registros", "relatorio_segmentacao.json"}
    if saida.exists() and any(path.name not in permitidos for path in saida.iterdir()):
        raise FileExistsError(
            "A saída contém arquivos que não pertencem a este pipeline."
        )
    cards = _carregar_cartoes(originais)
    if somente_placa is not None:
        cards = [card for card in cards if card.nome == somente_placa]
        if not cards:
            raise ValueError(f"Placa não encontrada: {somente_placa}.")
    if limite_placas is not None:
        cards = cards[:limite_placas]
    if recortes_saida.exists():
        permitidos_recortes = {"catalogos", ".staging", "configuracao.json"}
        ids_cartoes = {card.nome for card in cards}
        desconhecidos = [
            path.name
            for path in recortes_saida.iterdir()
            if path.name not in permitidos_recortes and path.name not in ids_cartoes
        ]
        if desconhecidos:
            raise FileExistsError(
                "A biblioteca contém diretórios fora do inventário COCO."
            )
    (saida / "mascaras").mkdir(parents=True, exist_ok=True)
    (saida / "registros").mkdir(parents=True, exist_ok=True)
    recortes_saida.mkdir(parents=True, exist_ok=True)
    if limite_anotacoes is not None and limite_anotacoes < 1:
        raise ValueError("--limite-anotacoes deve ser positivo.")
    if limite_placas is not None and limite_placas < 1:
        raise ValueError("--limite-placas deve ser positivo.")
    inicio = time.perf_counter()
    amostra: list[tuple[Any, dict[str, Any]]] = []
    restantes = limite_anotacoes
    for card in cards:
        if not card.caminho.resolve().is_relative_to(originais.resolve()):
            raise ValueError("Original fora da raiz confiável.")
        tones = _carregar_tons(card)
        annotations = [
            {**item, "taxon": tones.get(item.get("category_id"))}
            for item in card.anotacoes
        ]
        if restantes is not None:
            annotations = annotations[:restantes]
            restantes -= len(annotations)
        amostra.append((card, {"anotacoes": annotations}))
        if restantes is not None and restantes <= 0:
            break
    checkpoint_hash = hash_arquivo(checkpoint)
    registros = []
    pendentes = []
    for card, info in amostra:
        pronto = _placa_completa(
            card, saida, recortes_saida, reduzidas, checkpoint_hash
        )
        if pronto is None:
            pendentes.append((card, info))
        else:
            registros.append(pronto)
            print(
                f"Retomada: {card.nome} já conferida "
                f"({pronto['mascaras_aprovadas']}/{pronto['caixas_coco']}).",
                flush=True,
            )
    wrapper = _carregar_sam(checkpoint) if pendentes else None
    total = sum(len(info["anotacoes"]) for _, info in amostra)
    processadas = sum(registro["caixas_coco"] for registro in registros)
    for indice, (card, info) in enumerate(pendentes, start=1):
        imagem_modelo = reduzidas / "imagens" / f"{card.nome}.png"
        transformacao = _transformacao(card, imagem_modelo)
        staging_root = recortes_saida / ".staging"
        staging_plate = staging_root / card.nome
        if staging_plate.exists():
            if not _dentro_de(staging_plate, recortes_saida):
                raise ValueError("Staging de recorte fora da pasta autorizada.")
            shutil.rmtree(staging_plate)
        staging_plate.mkdir(parents=True, exist_ok=True)
        registro = processar_placa(
            card,
            reduzidas,
            saida,
            staging_plate,
            transformacao,
            wrapper.preditor,
            wrapper.torch,
            checkpoint_hash,
            anotacoes=info["anotacoes"],
        )
        final_plate = recortes_saida / card.nome
        if final_plate.exists():
            if not _dentro_de(final_plate, recortes_saida):
                raise ValueError("Recorte fora da pasta autorizada.")
            shutil.rmtree(final_plate)
        recortes_prontos = staging_plate / card.nome
        if recortes_prontos.is_dir():
            os.replace(recortes_prontos, final_plate)
        catalogo_staging = staging_plate / "catalogos" / f"{card.nome}.jsonl"
        if catalogo_staging.is_file():
            catalogos = recortes_saida / "catalogos"
            catalogos.mkdir(parents=True, exist_ok=True)
            os.replace(catalogo_staging, catalogos / catalogo_staging.name)
        if _dentro_de(staging_plate, recortes_saida):
            shutil.rmtree(staging_plate)
        registros.append(registro)
        processadas += registro["caixas_coco"]
        print(
            f"[{indice}/{len(amostra)}] {card.nome}: "
            f"{registro['mascaras_aprovadas']}/{registro['caixas_coco']} "
            f"({registro['taxa_aprovacao']:.1%}) — {processadas}/{total}",
            flush=True,
        )
    registros.sort(key=lambda r: r["placa"])
    resumo = {
        "versao": VERSAO,
        "tempo_segundos": time.perf_counter() - inicio,
        "checkpoint_sha256": checkpoint_hash,
        "placas": len(registros),
        "caixas_coco": sum(r["caixas_coco"] for r in registros),
        "mascaras_aprovadas": sum(r["mascaras_aprovadas"] for r in registros),
        "taxa_aprovacao": sum(r["mascaras_aprovadas"] for r in registros)
        / max(1, sum(r["caixas_coco"] for r in registros)),
        "erro_projecao_por_placa": {
            r["placa"]: r["erro_projecao_agregado"] for r in registros
        },
        "limites_qc": {
            "razao_area_caixa": [0.25, 1.0],
            "cobertura_bbox_coco_minima": 0.60,
            "componente": "maior componente 8-conexo",
        },
        "lotes_predicao": LOTE_PREDICAO,
        "margem_minima_original_px": MARGEM_MINIMA,
        "fator_margem": FATOR_MARGEM,
        "tamanho_recorte_px": [TAMANHO_MINIMO_RECORTE, TAMANHO_MAXIMO_RECORTE],
    }
    (saida / "relatorio_segmentacao.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (recortes_saida / "configuracao.json").write_text(
        json.dumps(
            {
                "versao": VERSAO,
                "checkpoint_sha256": resumo["checkpoint_sha256"],
                "recortes_por_placa": {
                    registro["placa"]: sum(
                        1 for item in registro["anotacoes"] if item["aprovada"]
                    )
                    for registro in registros
                },
                "proveniencia": "Caixa COCO humana, taxon e SHA-256 da imagem original; RGB e máscara SAM reduzidos à resolução do modelo.",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return resumo


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--originais", type=Path, required=True)
    parser.add_argument("--reduzidas", type=Path, required=True)
    parser.add_argument("--saida", type=Path, required=True)
    parser.add_argument("--recortes-saida", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--limite-anotacoes", type=int)
    parser.add_argument("--limite-placas", type=int)
    parser.add_argument("--somente-placa")
    args = parser.parse_args()
    print(json.dumps(executar(**vars(args)), ensure_ascii=False))
