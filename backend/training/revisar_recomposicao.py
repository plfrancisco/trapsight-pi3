"""Audita uma amostra e produz 30 casos altos e a calibração por colagens."""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from training.dataset_sintetico import (
    ConfiguracaoDataset,
    _carregar_base_real,
    _comparar_descritores_visuais,
    _compor_recortes_reais,
    _criar_base_sintetica,
    _descritores_visuais,
    _extrair_recortes_reais,
    calcular_percentual_cobertura,
    generate_dataset,
)


def painel(raiz: Path, registros: list[dict], nome: str) -> None:
    """Mostra todos os pares da amostra com cobertura e procedência."""
    folha = Image.new("RGB", (5 * 256, ((len(registros) + 4) // 5) * 216), "white")
    desenho = ImageDraw.Draw(folha)
    for i, r in enumerate(registros):
        with Image.open(raiz / "imagens" / f"{r['id']}.png") as imagem:
            foto = imagem.convert("RGB").resize((256, 192))
        x, y = (i % 5) * 256, (i // 5) * 216
        folha.paste(foto, (x, y))
        desenho.text((x + 3, y + 193), f"{r['id']} | {r['conjunto']}", fill="black")
        desenho.text(
            (x + 3, y + 204),
            f"alvo {r['percentual_cobertura_alvo']:.1f}% | real {r['percentual_cobertura_real']:.1f}%",
            fill="black",
        )
    folha.save(raiz / nome)


def auditar(raiz: Path) -> dict:
    """Recalcula todas as máscaras, integridade e interseções de fontes."""
    registros = [
        json.loads(linha)
        for linha in (raiz / "metadados.jsonl").read_text("utf-8").splitlines()
    ]
    donos: dict[str, set[str]] = {}
    for r in registros:
        fontes = set(r["placas_origem_recortes"])
        if r["placa_base_id"]:
            fontes.add(r["placa_base_id"])
        for fonte in fontes:
            donos.setdefault(fonte, set()).add(r["conjunto"])
        with Image.open(raiz / "mascaras" / f"{r['id']}.png") as mascara:
            assert set(np.unique(np.array(mascara))) <= {0, 1, 2, 255}
            assert (
                abs(
                    calcular_percentual_cobertura(mascara)
                    - r["percentual_cobertura_real"]
                )
                < 1e-8
            )
        with Image.open(raiz / "imagens" / f"{r['id']}.png") as imagem:
            assert imagem.size == (768, 576)
            imagem.verify()
    cruzadas = {p: sorted(c) for p, c in donos.items() if len(c) > 1}
    if cruzadas:
        raise ValueError(f"Fontes cruzadas: {cruzadas}")
    painel(raiz, registros, "painel_30.png")
    return {
        "amostras": len(registros),
        "cruzamentos": cruzadas,
        "divisoes": dict(Counter(r["conjunto"] for r in registros)),
        "faixas_alvo": dict(Counter(r["faixa_cobertura_alvo"] for r in registros)),
        "alvos_atingidos": sum(r["alvo_atingido"] for r in registros),
        "distratores": dict(
            Counter(d for r in registros for d in r["distratores_presentes"])
        ),
        "correlacao_idade_cobertura": float(
            np.corrcoef(
                [r["idade_simulada_dias"] for r in registros],
                [r["percentual_cobertura_real"] for r in registros],
            )[0, 1]
        ),
    }


def executar(amostra: Path, fonte: Path, mascaras: Path, saida: Path) -> dict:
    """Mantém a mesma divisão de fontes ao diagnosticar cobertura alta."""
    if saida.exists() and any(saida.iterdir()):
        raise FileExistsError(f"A saída precisa ser nova: {saida}")
    if not (amostra / "metadados.jsonl").exists():
        generate_dataset(
            ConfiguracaoDataset(
                diretorio_saida=amostra,
                diretorio_placas_reais=fonte,
                diretorio_mascaras_bases=mascaras,
                semente=20261021,
                idade_maxima_dias=90,
                quantidade=30,
                resolucao=(768, 576),
                limite_sprites=12000,
                limite_reuso_recorte=12,
            )
        )
    (saida / "imagens").mkdir(parents=True)
    (saida / "mascaras").mkdir()
    relatorio = json.loads((amostra / "relatorio_geracao.json").read_text("utf-8"))
    configuracao = json.loads((amostra / "configuracao.json").read_text("utf-8"))
    pools, bases = {}, {}
    for conjunto, info in relatorio["fontes_por_conjunto"].items():
        placas = tuple(
            _carregar_base_real(fonte / "imagens" / f"{p}.png", fonte, (768, 576))
            for p in info["placas_origem"]
        )
        pools[conjunto] = _extrair_recortes_reais(placas)[0]
        bases[conjunto] = [
            _carregar_base_real(
                fonte / "imagens" / f"{p}.png", fonte, (768, 576), mascaras
            )
            for p in info["bases_reais"]
        ]
    registros, descritores = [], []
    for i in range(30):
        conjunto = ("treino", "validacao", "teste")[i % 3]
        semente = configuracao["semente_global"] ^ (0xA170000 + i)
        rng = random.Random(semente)
        base = rng.choice(bases[conjunto])
        real = i % 2 == 0
        imagem, mascara = (
            (base.imagem.copy(), base.mascara.copy())
            if real
            else _criar_base_sintetica((768, 576), rng)
        )
        alvo = rng.uniform(51.0, 55.0)
        imagem, mascara, meta = _compor_recortes_reais(
            imagem,
            mascara,
            pools[conjunto],
            alvo,
            rng,
            12000,
            12,
            0.7,
            [0] * len(pools[conjunto]),
        )
        meta.pop("_indices_recortes_usados")
        registro = {
            **meta,
            "id": f"alto_{i + 1:06d}",
            "conjunto": conjunto,
            "semente": semente,
            "percentual_cobertura_alvo": alvo,
            "placa_base_id": base.identificador if real else None,
        }
        registros.append(registro)
        imagem.save(saida / "imagens" / f"{registro['id']}.png")
        mascara.save(saida / "mascaras" / f"{registro['id']}.png")
        descritores.append(_descritores_visuais(imagem, mascara))
    altos = sum(r["percentual_cobertura_real"] >= 50 for r in registros)
    if altos < 30:
        raise ValueError(f"Só {altos}/30 casos atingiram cobertura real >=50%.")
    avaliacao = [
        _carregar_base_real(fonte / "imagens" / f"{p}.png", fonte, (768, 576))
        for p in relatorio["separacao_placas"]["avaliacao"]
    ]
    comparacao = _comparar_descritores_visuais(
        descritores, [_descritores_visuais(b.imagem, b.mascara) for b in avaliacao]
    )
    calibracao = []
    base = bases["treino"][0]
    for limite, referencia in ((300, 14.38), (900, 34.65), (2200, 62.62)):
        _, _, meta = _compor_recortes_reais(
            base.imagem,
            base.mascara,
            pools["treino"],
            90.0,
            random.Random(20261021),
            limite,
            12,
            0.7,
            [0] * len(pools["treino"]),
        )
        cobertura = meta["percentual_cobertura_real"]
        calibracao.append(
            {
                "limite_colagens": limite,
                "coladas": meta["n_recortes"],
                "cobertura": cobertura,
                "referencia": referencia,
                "razao": cobertura / referencia,
            }
        )
    (saida / "metadados.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in registros),
        encoding="utf-8",
    )
    painel(saida, registros, "painel_altos_30.png")
    final = {
        "amostra": auditar(amostra),
        "fontes_por_conjunto": relatorio["fontes_por_conjunto"],
        "diagnostico_casos_altos": altos,
        "descritores_cobertura_alta": comparacao,
        "calibracao_treino": calibracao,
        "avaliacao_real_rotulo_incompleto": True,
        "tipo": "Diagnóstico independente, sem integrar o dataset de treino.",
    }
    (saida / "relatorio_revisao.json").write_text(
        json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return final


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for nome in ("amostra", "fonte", "mascaras", "saida"):
        parser.add_argument(f"--{nome}", type=Path, required=True)
    args = parser.parse_args()
    resultado = executar(args.amostra, args.fonte, args.mascaras, args.saida)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
