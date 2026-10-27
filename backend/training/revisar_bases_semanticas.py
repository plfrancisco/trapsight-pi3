"""Materializa anotações versionadas, mede o aceite e prepara conferência visual.

O limiar só localiza candidatas. As classes e silhuetas são lidas das anotações,
sem converter componentes escuros em gabarito. Uma revisão pendente não autoriza
usar estas máscaras na geração de um dataset.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from training.dataset_sintetico import NOMES_BASES_REAIS
from training.estruturas_bases import (
    aplicar_decisoes,
    carregar_estruturas,
    inventariar,
    medir_decisoes,
    restaurar_rle,
    validar_inventario,
)

VERSAO = "bases_semanticas_v5"
CORES = {"inseto": (235, 40, 70), "sujeira": (20, 180, 80), "ambigua": (255, 170, 0)}


def sha256(arquivo: Path) -> str:
    return hashlib.sha256(arquivo.read_bytes()).hexdigest()


def executar(fonte: Path, anotacoes: Path, saida: Path) -> dict:
    """Recusa inventários alterados e nunca promove a revisão automaticamente."""
    if saida.exists() and any(saida.iterdir()):
        raise FileExistsError("A saída deve ser uma pasta nova.")
    (saida / "mascaras").mkdir(parents=True)
    registros = []
    for nome in NOMES_BASES_REAIS:
        identificador = Path(nome).stem
        pasta = anotacoes / identificador
        imagem = fonte / "imagens" / nome
        original_path = fonte / "mascaras" / nome
        rgb = np.array(Image.open(imagem).convert("RGB"))
        original = np.array(Image.open(original_path).convert("L"))
        placa, estruturas, estruturas_dados = carregar_estruturas(
            pasta / "estruturas.json", imagem
        )
        decisoes = json.loads((pasta / "regioes.json").read_text("utf-8"))
        adicionais = json.loads((pasta / "insetos_adicionais.json").read_text("utf-8"))
        if decisoes["estruturas_sha256"] != sha256(pasta / "estruturas.json"):
            raise ValueError("As estruturas mudaram desde o inventário.")
        if decisoes["mascara_original_sha256"] != sha256(original_path):
            raise ValueError("A anotação original mudou desde a revisão.")
        if adicionais["imagem_sha256"] != sha256(imagem):
            raise ValueError("As silhuetas SAM pertencem a outra imagem.")
        regioes = decisoes["regioes"]
        labels, inventario = inventariar(rgb, placa, estruturas, regioes)
        validar_inventario(regioes, inventario)
        silhuetas = (original == 2) & ~estruturas
        for regiao in adicionais["regioes"]:
            if regiao["decisao"] != "inseto":
                raise ValueError(
                    "Silhueta adicional precisa de decisão semântica explícita."
                )
            silhuetas |= restaurar_rle(regiao["mascara_rle"], original.shape)
        for regiao in regioes:
            if "mascara_sam_rle" in regiao:
                if regiao["decisao"] != "inseto":
                    raise ValueError("SAM não pode alterar a decisão semântica.")
                silhuetas |= restaurar_rle(regiao["mascara_sam_rle"], original.shape)
        nova = aplicar_decisoes(placa, estruturas, labels, regioes, silhuetas)
        destino = saida / "mascaras" / nome
        Image.fromarray(nova).save(destino)
        medidas = medir_decisoes(labels, regioes, original, placa)
        candidata = labels > 0
        medidas["area_candidata_por_classe_final_px"] = {
            str(c): int(np.count_nonzero(candidata & (nova == c)))
            for c in (0, 1, 2, 255)
        }
        medidas["area_candidata_rotulada_depois_px"] = medidas[
            "area_candidata_por_classe_final_px"
        ]["2"]
        medidas["completude_area_depois"] = medidas[
            "area_candidata_rotulada_depois_px"
        ] / max(1, medidas["area_candidata_total_px"])
        medidas["regioes_inseto_com_silhueta_insuficiente"] = [
            r["id"]
            for r in regioes
            if r["decisao"] == "inseto"
            and np.count_nonzero((labels == r["id"]) & (nova == 2))
            < r["area_candidata_px"] / 2
        ]
        medidas["pixels_fundo_corrigidos_para_inseto"] = int(
            np.count_nonzero((original == 0) & (nova == 2))
        )
        visual = rgb.copy()
        visual[estruturas] = (
            visual[estruturas] * 0.4 + np.array((0, 190, 230)) * 0.6
        ).astype(np.uint8)
        for classe, cor in ((2, CORES["inseto"]), (255, CORES["ambigua"])):
            pixels = nova == classe
            visual[pixels] = (visual[pixels] * 0.4 + np.array(cor) * 0.6).astype(
                np.uint8
            )
        painel = Image.new("RGB", (1536, 606), "white")
        painel.paste(Image.fromarray(rgb), (0, 30))
        painel.paste(Image.fromarray(visual), (768, 30))
        ImageDraw.Draw(painel).text(
            (8, 8),
            "Original | vermelho: inseto; laranja: ambigua; ciano: estrutura. PROVISORIO",
            fill="black",
        )
        painel.save(saida / f"conferencia_{nome}")
        # Todo candidato aparece no catálogo, inclusive componentes de um pixel.
        catalogo = Image.new("RGB", (960, 100 * ((len(regioes) + 11) // 12)), "white")
        desenho = ImageDraw.Draw(catalogo)
        for i, regiao in enumerate(regioes):
            x, y, w, h = regiao["caixa"]
            recorte = Image.fromarray(rgb).crop(
                (max(0, x - 7), max(0, y - 7), min(768, x + w + 7), min(576, y + h + 7))
            )
            recorte.thumbnail((76, 72))
            recorte = recorte.resize((76, 72), Image.Resampling.NEAREST)
            xx, yy = (i % 12) * 80, (i // 12) * 100
            catalogo.paste(recorte, (xx, yy))
            cor = CORES.get(regiao["decisao"], (0, 0, 0))
            desenho.text(
                (xx, yy + 73),
                f"{regiao['id']}: {regiao['area_candidata_px']}px",
                fill="black",
            )
            desenho.text((xx, yy + 85), regiao["decisao"] or "pendente", fill=cor)
        catalogo.save(saida / f"regioes_{nome}")
        registros.append(
            {
                "placa": identificador,
                "revisao_visual": (
                    "aprovada"
                    if all(
                        d.get("revisao_visual") == "aprovada"
                        for d in (estruturas_dados, decisoes, adicionais)
                    )
                    else "pendente"
                ),
                "medidas": medidas,
                "sha256_original": sha256(original_path),
                "sha256_complementar": sha256(destino),
                "anotacoes_sha256": {
                    p.name: sha256(p) for p in sorted(pasta.glob("*.json"))
                },
            }
        )
    relatorio = {
        "versao": VERSAO,
        "revisao_visual": (
            "aprovada"
            if all(
                p["revisao_visual"] == "aprovada" and p["medidas"]["aceita"]
                for p in registros
            )
            else "pendente"
        ),
        "placas": registros,
        "aceite_por_area": all(p["medidas"]["aceita"] for p in registros),
        "avaliacao_real": "As 14 placas de avaliação mantêm os rótulos originais incompletos.",
        "limitação": "Não usar como gabarito aprovado enquanto a revisão semântica estiver pendente.",
    }
    (saida / "configuracao.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    linhas = [
        "# Revisão semântica provisória das seis bases",
        "",
        "Não autoriza gerar a amostra ou o dataset. Vermelho: inseto; laranja: ambiguidade; ciano: estrutura.",
        "",
        "| Placa | Candidata px | Classe 2 antes | Classe 2 depois | Inseto px | Sujeira px | Ambígua px | Ambígua % candidata | Ambígua pp placa | Aceite de área |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for p in registros:
        m = p["medidas"]
        a = m["areas_candidatas_px"]
        linhas.append(
            f"| {p['placa']} | {m['area_candidata_total_px']} | {100 * m['completude_area_antes']:.2f}% | {100 * m['completude_area_depois']:.2f}% | {a['inseto']} | {a['sujeira']} | {a['ambigua']} | {100 * m['fracao_area_ambigua']:.2f}% | {m['area_ambigua_pp_placa']:.3f} | {m['aceita']} |"
        )
    linhas.extend(
        [
            "",
            "As áreas são do inventário fixo de candidatas; silhuetas SAM podem incluir asas claras fora dessas regiões.",
            "",
            "As decisões herdadas de anotação anterior são identificadas no JSON. Regiões sem evidência semântica suficiente permanecem ambíguas, sem promoção automática por brilho ou área.",
            "",
            relatorio["avaliacao_real"],
        ]
    )
    (saida / "relatorio.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return relatorio


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fonte", type=Path, required=True)
    parser.add_argument(
        "--anotacoes", type=Path, default=Path(__file__).with_name("anotacoes_ums")
    )
    parser.add_argument("--saida", type=Path, required=True)
    args = parser.parse_args()
    resultado = executar(args.fonte, args.anotacoes, args.saida)
    print(
        json.dumps(
            {
                "aceite_por_area": resultado["aceite_por_area"],
                "revisao_visual": resultado["revisao_visual"],
            }
        )
    )
