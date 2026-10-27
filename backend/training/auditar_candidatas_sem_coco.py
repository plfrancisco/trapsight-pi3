"""Audita candidatas escuras sem caixa COCO em recortes dos originais UMS.

As classificações são visuais e independentes do brilho. O limiar apenas
identifica regiões candidatas e a caixa COCO ausente não conta como evidência.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from training.teste_real_ums import _carregar_cartoes

SEMENTE_AUDITORIA = 20261021
QUANTIDADE_AUDITORIA = 300
TAMANHO_CELULA = (190, 164)
TAMANHO_PREVIA = (128, 128)
CORES_DECISAO = {
    "inseto": (166, 34, 45),
    "sujeira": (20, 125, 72),
    "ambigua": (194, 113, 0),
}


def hash_arquivo(caminho: Path) -> str:
    """Hash em blocos para registrar a versão dos originais revisados."""
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def intervalo_wilson(sucessos: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Intervalo de confiança de Wilson para uma proporção binomial."""
    if total <= 0 or not 0 <= sucessos <= total:
        raise ValueError("Contagens da proporção são inválidas.")
    proporcao = sucessos / total
    denominador = 1 + z * z / total
    centro = (proporcao + z * z / (2 * total)) / denominador
    margem = (
        z
        * ((proporcao * (1 - proporcao) / total + z * z / (4 * total**2)) ** 0.5)
        / denominador
    )
    return max(0.0, centro - margem), min(1.0, centro + margem)


def selecionar_amostra(
    candidatas: list[dict[str, Any]], quantidade: int, semente: int
) -> list[dict[str, Any]]:
    """Sorteia regiões sem caixa COCO de uma população ordenada e revisada."""
    if quantidade < 1 or quantidade > len(candidatas):
        raise ValueError("A amostra precisa caber na população de candidatas.")
    ordenadas = sorted(candidatas, key=lambda r: (r["placa"], str(r["id"])))
    return random.Random(semente).sample(ordenadas, quantidade)


def _carregar_populacao(
    anotacoes: Path,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    candidatas = []
    por_placa = {}
    for pasta in sorted(anotacoes.iterdir()):
        arquivo = pasta / "regioes.json"
        if not arquivo.is_file():
            continue
        documento = json.loads(arquivo.read_text("utf-8"))
        regioes = documento.get("regioes", [])
        por_placa[pasta.name] = documento
        for regiao in regioes:
            evidencia = regiao.get("evidencia", {})
            if evidencia.get("coco"):
                continue
            if regiao.get("revisao_visual") != "aprovada":
                raise ValueError(
                    f"Candidata ainda não foi revisada: {pasta.name}/{regiao['id']}."
                )
            if regiao.get("decisao") not in CORES_DECISAO:
                raise ValueError(f"Candidata sem decisão: {pasta.name}/{regiao['id']}.")
            candidatas.append(
                {
                    "placa": pasta.name,
                    "id": regiao["id"],
                    "decisao": regiao["decisao"],
                    "area_candidata_px": int(regiao["area_candidata_px"]),
                    "bbox_reduzida_xywh": list(regiao["caixa"]),
                    "bbox_original_xyxy": list(evidencia["recorte_original_xyxy"]),
                    "tamanho_original_px": list(
                        evidencia["tamanho_candidata_original_px"]
                    ),
                    "coco": evidencia.get("coco", []),
                    "coco_sha256": evidencia.get("coco_sha256"),
                    "origem_decisao": regiao["origem_decisao"],
                }
            )
    if not candidatas:
        raise ValueError("Não foram encontradas candidatas sem caixa COCO revisadas.")
    return candidatas, por_placa


def _painel(
    itens: list[dict[str, Any]],
    previas: dict[tuple[str, int], Image.Image],
    destino: Path,
    pagina: int,
) -> None:
    """Salva vinte recortes nativos por painel, incluindo ID e classe revisada."""
    colunas, linhas = 4, 5
    largura = colunas * TAMANHO_CELULA[0]
    altura = 28 + linhas * TAMANHO_CELULA[1]
    painel = Image.new("RGB", (largura, altura), "white")
    desenho = ImageDraw.Draw(painel)
    desenho.text(
        (8, 7),
        f"Auditoria aleatória {pagina:02d} | recorte original 256 × 256",
        fill="black",
    )
    for indice, item in enumerate(itens):
        x, y = (
            (indice % colunas) * TAMANHO_CELULA[0],
            28 + (indice // colunas) * TAMANHO_CELULA[1],
        )
        figura = previas[(item["placa"], int(item["id"]))].resize(
            TAMANHO_PREVIA, Image.Resampling.LANCZOS
        )
        painel.paste(figura, (x + 4, y + 4))
        figura.close()
        rotulo = f"{item['placa'][-4:]} · {item['id']} · {item['decisao']}"
        desenho.text((x + 4, y + 136), rotulo, fill=CORES_DECISAO[item["decisao"]])
        desenho.text(
            (x + 4, y + 150),
            f"{item['tamanho_original_px'][0]:.0f}×{item['tamanho_original_px'][1]:.0f} px nativos",
            fill=(70, 70, 70),
        )
    destino.parent.mkdir(parents=True, exist_ok=True)
    painel.save(destino, format="PNG", optimize=True)
    painel.close()


def executar(
    originais: Path,
    anotacoes: Path,
    saida: Path,
    quantidade: int = QUANTIDADE_AUDITORIA,
    semente: int = SEMENTE_AUDITORIA,
) -> dict[str, Any]:
    """Gera a amostra visual, estima p e registra proveniência da revisão."""
    if saida.exists() and any(saida.iterdir()):
        raise FileExistsError("A saída da auditoria precisa ser nova ou vazia.")
    saida.mkdir(parents=True, exist_ok=True)
    populacao, por_placa = _carregar_populacao(anotacoes)
    amostra = selecionar_amostra(populacao, quantidade, semente)
    contagens = Counter(item["decisao"] for item in amostra)
    total = len(amostra)
    insetos = contagens["inseto"]
    ambiguas = contagens["ambigua"]
    inferior = intervalo_wilson(insetos, total)
    superior = intervalo_wilson(insetos + ambiguas, total)
    razoes_por_placa = defaultdict(list)
    for item in amostra:
        razoes_por_placa[item["placa"]].append(item)

    cartoes = {cartao.nome: cartao for cartao in _carregar_cartoes(originais)}
    previas: dict[tuple[str, int], Image.Image] = {}
    hashes_originais = {}
    for placa in sorted(razoes_por_placa):
        cartao = cartoes[placa]
        if not cartao.caminho.resolve().is_relative_to(originais.resolve()):
            raise ValueError("Original fora da raiz confiável.")
        hashes_originais[placa] = hash_arquivo(cartao.caminho)
        limite_anterior = Image.MAX_IMAGE_PIXELS
        try:
            Image.MAX_IMAGE_PIXELS = None
            with Image.open(cartao.caminho) as original:
                original.load()
                for item in razoes_por_placa[placa]:
                    janela = tuple(item["bbox_original_xyxy"])
                    previa = original.crop(janela).transpose(Image.Transpose.ROTATE_90)
                    if previa.size != (256, 256):
                        previa = previa.resize((256, 256), Image.Resampling.LANCZOS)
                    previas[(placa, int(item["id"]))] = previa
        finally:
            Image.MAX_IMAGE_PIXELS = limite_anterior

    paginas = [amostra[i : i + 20] for i in range(0, total, 20)]
    for pagina, itens in enumerate(paginas, start=1):
        _painel(
            itens,
            previas,
            saida / "paineis" / f"auditoria_{pagina:02d}.png",
            pagina,
        )
    for previa in previas.values():
        previa.close()

    registros = []
    for indice, item in enumerate(amostra, start=1):
        registros.append(
            {
                "amostra_id": indice,
                **item,
                "revisao_visual": "aprovada_no_original",
                "sha256_original": hashes_originais[item["placa"]],
            }
        )
    proporcao = insetos / total
    risco = (insetos + ambiguas) / total
    por_placa_relatorio = []
    for placa, documento in sorted(por_placa.items()):
        regioes = [
            r for r in documento["regioes"] if not r.get("evidencia", {}).get("coco")
        ]
        por_placa_relatorio.append(
            {
                "placa": placa,
                "pool_sem_coco": len(regioes),
                "amostradas": sum(item["placa"] == placa for item in amostra),
                "decisoes_pool": dict(Counter(r["decisao"] for r in regioes)),
                "area_pool_sem_coco_px": sum(
                    int(r["area_candidata_px"]) for r in regioes
                ),
            }
        )
    relatorio = {
        "versao": "auditoria_sem_coco_v5",
        "semente": semente,
        "populacao_sem_coco": len(populacao),
        "amostra": total,
        "decisoes": dict(contagens),
        "p_insetos_confirmados": proporcao,
        "p_insetos_confirmados_ic95_wilson": list(inferior),
        "p_risco_inseto_mais_ambiguo": risco,
        "p_risco_ic95_wilson": list(superior),
        "limiar_p": 0.05,
        "regra_aplicada": "p acima de 5%: candidatas não anotadas sem decisão visual ficam em 255; sujeira confirmada permanece classe 1.",
        "placas": por_placa_relatorio,
        "itens": registros,
    }
    (saida / "auditoria.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return relatorio


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--originais", type=Path, required=True)
    parser.add_argument("--anotacoes", type=Path, required=True)
    parser.add_argument("--saida", type=Path, required=True)
    parser.add_argument("--quantidade", type=int, default=QUANTIDADE_AUDITORIA)
    parser.add_argument("--semente", type=int, default=SEMENTE_AUDITORIA)
    args = parser.parse_args()
    resultado = executar(**vars(args))
    print(
        json.dumps(
            {k: v for k, v in resultado.items() if k != "itens"}, ensure_ascii=False
        )
    )
