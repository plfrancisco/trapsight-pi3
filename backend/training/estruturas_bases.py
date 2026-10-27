"""Máscaras de estruturas e inventário de regiões com decisões independentes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from training.medicoes_recomposicao import cinza_fixo


def restaurar_rle(linhas: list[list[int]], formato: tuple[int, int]) -> np.ndarray:
    """Decodifica intervalos exclusivos, recusando coordenadas inválidas."""
    mascara = np.zeros(formato, dtype=bool)
    altura, largura = formato
    for y, x0, x1 in linhas:
        if not (0 <= y < altura and 0 <= x0 < x1 <= largura):
            raise ValueError("Intervalo RLE fora da imagem.")
        mascara[y, x0:x1] = True
    return mascara


def carregar_estruturas(arquivo: Path, imagem: Path):
    """Restaura a máscara desenhada e versionada, sem classificar por cor."""
    dados = json.loads(arquivo.read_text("utf-8"))
    if hashlib.sha256(imagem.read_bytes()).hexdigest() != dados["imagem_sha256"]:
        raise ValueError("A imagem mudou desde a revisão das estruturas.")
    mascara = restaurar_rle(dados["estruturas_rle"], (576, 768))
    mascara |= restaurar_rle(dados.get("refinamentos_rle", []), (576, 768))
    placa = Image.new("L", (768, 576), 0)
    ImageDraw.Draw(placa).polygon([tuple(p) for p in dados["placa_poligono"]], fill=1)
    return np.array(placa).astype(bool), mascara, dados


def inventariar(
    rgb: np.ndarray,
    placa: np.ndarray,
    estruturas: np.ndarray,
    ids_estaveis: list[dict] | None = None,
):
    """Detecta caixas candidatas; não descarta insetos grandes nem dá a classe."""
    cinza = cinza_fixo(rgb)
    candidata = placa & ~estruturas & (cinza < float(np.median(cinza[placa])) - 35)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(
        candidata.astype(np.uint8), connectivity=8
    )
    regioes = []
    for indice in range(1, n):
        x, y, w, h, area = map(int, stats[indice])
        regioes.append(
            {
                "id": indice,
                "caixa": [x, y, w, h],
                "area_candidata_px": area,
                "decisao": None,
            }
        )
    if ids_estaveis is not None:
        anteriores = {
            (tuple(r["caixa"]), r["area_candidata_px"]): r["id"] for r in ids_estaveis
        }
        mapa = np.zeros(n, np.int32)
        for regiao in regioes:
            chave = (tuple(regiao["caixa"]), regiao["area_candidata_px"])
            if chave not in anteriores:
                raise ValueError(
                    "A geometria mudou; é necessário revisar a identidade das regiões."
                )
            novo_id = anteriores[chave]
            mapa[regiao["id"]] = novo_id
            regiao["id"] = novo_id
        labels = mapa[labels]
        regioes.sort(key=lambda regiao: regiao["id"])
    return labels, regioes


def validar_inventario(regioes: list[dict], esperado: list[dict]) -> None:
    """Uma alteração de geometria exige revisar de novo as decisões por região."""
    campos = ("id", "caixa", "area_candidata_px")
    if len(regioes) != len(esperado) or any(
        any(regiao[campo] != referencia[campo] for campo in campos)
        for regiao, referencia in zip(regioes, esperado, strict=True)
    ):
        raise ValueError(
            "Inventário mudou; decisões antigas não podem ser reaplicadas."
        )


def aplicar_decisoes(
    placa: np.ndarray,
    estruturas: np.ndarray,
    labels: np.ndarray,
    regioes: list[dict],
    silhuetas: np.ndarray,
) -> np.ndarray:
    """Aplica decisões sem usar os pixels escuros como silhueta de insetos.

    As silhuetas vêm de anotações independentes/SAM, inclusive sobre buracos da
    máscara original. Sujeira confirmada permanece 1; só ambiguidade recebe 255.
    """
    resultado = placa.astype(np.uint8)
    resultado[placa & silhuetas] = 2
    resultado[placa & estruturas & ~silhuetas] = 1
    for regiao in regioes:
        componente = labels == regiao["id"]
        if regiao["decisao"] == "sujeira":
            resultado[componente] = 1
        elif regiao["decisao"] == "ambigua":
            resultado[componente] = 255
        elif regiao["decisao"] not in ("inseto", None):
            raise ValueError("Decisão sem classe conhecida.")
    return resultado


def validar_aceite_bases(manifesto: dict) -> None:
    """Aceita somente as bases listadas com máscaras e áreas de 255 verificadas."""
    erro = "As bases elegíveis exigem revisão semântica e aceite por área."
    if manifesto.get("versao") != "bases_semanticas_v5" or manifesto.get(
        "revisao_visual"
    ) not in ("aprovada", "parcialmente_aprovada"):
        raise ValueError(erro)
    placas = manifesto.get("placas", [])
    if not placas or len({p["placa"] for p in placas}) != len(placas):
        raise ValueError(erro)
    elegiveis = manifesto.get("bases_elegiveis", [])
    por_nome = {placa["placa"]: placa for placa in placas}
    if not elegiveis or len(set(elegiveis)) != len(elegiveis):
        raise ValueError(erro)
    for nome in elegiveis:
        placa = por_nome.get(nome)
        if placa is None or placa.get("revisao_visual") != "aprovada":
            raise ValueError(erro)
        medidas = placa.get("medidas", {})
        if (
            not medidas.get("aceita")
            or medidas.get("regioes", {}).get("sem_decisao", 1) != 0
            or medidas.get("area_255_pp", 100)
            > manifesto.get("limite_base_255_pp", 1.0)
            or not placa.get("base_elegivel")
        ):
            raise ValueError(erro)


def medir_decisoes(
    labels: np.ndarray, regioes: list[dict], original: np.ndarray, placa: np.ndarray
) -> dict:
    """Mede por área e cobra decisão explícita de cada candidata."""
    totais = {"inseto": 0, "sujeira": 0, "ambigua": 0, "sem_decisao": 0}
    contagens = dict.fromkeys(totais, 0)
    area_antes = 0
    for regiao in regioes:
        area = regiao["area_candidata_px"]
        decisao = regiao["decisao"] or "sem_decisao"
        if decisao not in totais:
            raise ValueError(f"Decisão desconhecida: {decisao}")
        totais[decisao] += area
        contagens[decisao] += 1
        area_antes += int(np.count_nonzero((labels == regiao["id"]) & (original == 2)))
    total = sum(totais.values())
    fracao_ambigua = totais["ambigua"] / max(1, total)
    ambigua_pp = 100 * totais["ambigua"] / max(1, int(placa.sum()))
    return {
        "regioes": contagens,
        "areas_candidatas_px": totais,
        "area_candidata_total_px": total,
        "area_candidata_rotulada_antes_px": area_antes,
        "completude_area_antes": area_antes / max(1, total),
        "fracao_area_ambigua": fracao_ambigua,
        "area_ambigua_pp_placa": ambigua_pp,
        "aceita": contagens["sem_decisao"] == 0
        and fracao_ambigua <= 0.1
        and ambigua_pp <= 0.2,
    }
