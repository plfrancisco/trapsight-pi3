"""Avaliação pareada, sem augmentation nem recalibração do baseline."""

from __future__ import annotations

import json
import math
import platform
import random
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
import torch
from PIL import Image

from training.baseline import ARQUIVO_CALIBRACAO_PADRAO, segmentar
from training.treino.aumentos import transformacao_avaliacao
from training.treino.dados import (
    InfoDataset,
    hash_arquivo,
    ler_dataset,
    verificar_estrutura,
    verificar_mascaras,
)
from training.treino.metricas import AcumuladorMetricas

SUBCONJUNTOS = ("iluminacao_angulo", "sujeira", "amarelamento")


def conferir_aprovacao(metricas: dict[str, Any], dominio: str) -> dict[str, Any]:
    """Confere alvo e mínimo de um domínio; rejeita domínio desconhecido.

    Um erro crítico reprova ambos os níveis, mesmo com médias aceitáveis.
    A aprovação de um domínio isolado não aprova o modelo para produção.
    """
    if dominio not in ("sintetico", "real"):
        raise ValueError("Domínio deve ser sintetico ou real.")
    limites = {
        "erro_percentual_medio_pp": (1.0, 2.0)
        if dominio == "sintetico"
        else (2.0, 3.0),
        "dice_coberta": (0.90, 0.85) if dominio == "sintetico" else (0.80, 0.75),
        "trocar_como_ok": (0, 0),
    }
    if dominio == "real":
        limites["acuracia_status"] = (0.90, 0.85)
    criterios = {}
    for nome, (alvo, minimo) in limites.items():
        valor = metricas[nome]
        menor = nome in ("erro_percentual_medio_pp", "trocar_como_ok")
        criterios[nome] = {
            "valor": valor,
            "alvo": alvo,
            "minimo": minimo,
            "atingiu_alvo": valor <= alvo if menor else valor >= alvo,
            "atingiu_minimo": valor <= minimo if menor else valor >= minimo,
        }
    return {
        "dominio": dominio,
        "criterios": criterios,
        "atingiu_alvo": all(c["atingiu_alvo"] for c in criterios.values()),
        "atingiu_minimo": all(c["atingiu_minimo"] for c in criterios.values()),
    }


def comparar_modelo_baseline(
    modelo: torch.nn.Module,
    info: InfoDataset,
    limiar_v: int,
    dominio: str = "sintetico",
    dispositivo: str = "cpu",
) -> dict[str, Any]:
    """Mede ambos os métodos nas mesmas amostras de teste e pixels válidos.

    Recebe um modelo carregado e limiar já calibrado. Retorna métricas globais,
    por condição, origem da base e idade exata; recusa teste vazio ou inválido.
    Rótulos de robustez são explícitos para não inventar cortes experimentais.
    """
    if dominio not in ("sintetico", "real"):
        raise ValueError("Domínio deve ser sintetico ou real.")
    amostras = info.do_conjunto("teste")
    if not amostras:
        raise ValueError("O conjunto de teste está vazio.")
    if any(not math.isfinite(a.idade_dias) or a.idade_dias < 0 for a in amostras):
        raise ValueError("Idades devem ser finitas e não negativas.")
    problemas = verificar_mascaras(amostras)
    if problemas:
        raise ValueError(" ".join(problemas))
    grupos: dict[str, dict[str, AcumuladorMetricas]] = {}
    registros = []
    transformacao = transformacao_avaliacao()
    modo_anterior = modelo.training
    modelo.to(dispositivo).eval()
    try:
        with torch.inference_mode():
            for amostra in amostras:
                with Image.open(amostra.imagem) as aberta:
                    imagem = np.array(aberta.convert("RGB"), dtype=np.uint8)
                with Image.open(amostra.mascara) as aberta:
                    mascara = np.array(aberta.convert("L"), dtype=np.uint8)
                if imagem.shape[:2] != mascara.shape:
                    raise ValueError(f"Dimensões divergentes: {amostra.identificador}.")
                entrada = transformacao(image=imagem, mask=mascara)
                logits = modelo(entrada["image"].unsqueeze(0).to(dispositivo)).cpu()
                alvo = torch.from_numpy(mascara.copy()).long().unsqueeze(0)
                placa = np.isin(mascara, (1, 2))
                coberta, _ = segmentar(imagem, limiar_v, placa)
                rotulos = np.where(placa, np.where(coberta > 0, 2, 1), 0)
                baseline = (
                    torch.nn.functional.one_hot(torch.from_numpy(rotulos).long(), 3)
                    .permute(2, 0, 1)
                    .unsqueeze(0)
                    .float()
                )
                chaves = [
                    "global",
                    f"base/{amostra.origem_base or 'nao_informada'}",
                    f"idade/{amostra.idade_dias}",
                ]
                chaves += [f"condicao/{s}" for s in amostra.subconjuntos_avaliacao]
                for chave in dict.fromkeys(chaves):
                    par = grupos.setdefault(
                        chave,
                        {
                            "modelo": AcumuladorMetricas(),
                            "baseline": AcumuladorMetricas(),
                        },
                    )
                    for metodo, predicao in (
                        ("modelo", logits),
                        ("baseline", baseline),
                    ):
                        par[metodo].atualizar(
                            predicao,
                            alvo,
                            [amostra.idade_dias],
                            [amostra.dominante_cor],
                        )
                registros.append(
                    {
                        "id": amostra.identificador,
                        "semente": amostra.semente,
                        "imagem_sha256": hash_arquivo(amostra.imagem),
                        "mascara_sha256": hash_arquivo(amostra.mascara),
                    }
                )
    finally:
        modelo.train(modo_anterior)
    resultados = {
        chave: {nome: acumulador.resultado() for nome, acumulador in par.items()}
        for chave, par in sorted(grupos.items())
    }
    global_ = resultados.pop("global")
    for metodo in ("modelo", "baseline"):
        for registro, metrica in zip(registros, global_[metodo]["por_imagem"]):
            metrica.update(registro)
    aprovacao = conferir_aprovacao(global_["modelo"], dominio)
    return {
        "modelo": global_["modelo"],
        "baseline": global_["baseline"],
        "por_base": {
            k.split("/", 1)[1]: v
            for k, v in resultados.items()
            if k.startswith("base/")
        },
        "por_subconjunto": {s: resultados.get(f"condicao/{s}") for s in SUBCONJUNTOS},
        "curvas_erro_por_idade": [
            {
                "idade_dias": float(k.split("/", 1)[1]),
                "amostras": v["modelo"]["amostras"],
                **{m: v[m]["erro_percentual_medio_pp"] for m in ("modelo", "baseline")},
            }
            for k, v in sorted(
                resultados.items(),
                key=lambda item: (
                    float(item[0].split("/", 1)[1])
                    if item[0].startswith("idade/")
                    else -1
                ),
            )
            if k.startswith("idade/")
        ],
        "aprovacao": aprovacao,
        # Recomposição sobre foto real continua pertencendo ao domínio sintético.
        "aprovacao_geral": (
            "pendente_outro_dominio" if aprovacao["atingiu_minimo"] else "reprovado"
        ),
        "subconjuntos_ausentes": [
            s for s in SUBCONJUNTOS if f"condicao/{s}" not in resultados
        ],
        "baseline_pressuposto": "recorte da placa pelo gabarito; limiar global fixo",
    }


def grafico_idade_svg(curvas: list[dict[str, Any]]) -> str:
    """Retorna SVG com duas curvas de erro médio por idade, sem dependências.

    Recusa curvas vazias; os pontos preservam as idades observadas no teste.
    """
    if not curvas:
        raise ValueError("Não há idades para o gráfico.")
    xmax = max(1.0, max(p["idade_dias"] for p in curvas))
    ymax = max(1.0, max(p[m] for p in curvas for m in ("modelo", "baseline")))
    partes = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="720" height="400" viewBox="0 0 720 400">',
        '<rect width="720" height="400" fill="white"/>',
        '<path d="M60 30V340H680" fill="none" stroke="black"/>',
        '<text x="280" y="390">Idade do refil (dias)</text>',
        '<text x="60" y="20">Erro absoluto médio (pp)</text>',
        f'<text x="15" y="40">{ymax:.2f}</text>',
        '<text x="35" y="355">0</text>',
        f'<text x="640" y="360">{xmax:g}</text>',
    ]
    for metodo, cor, y in (("modelo", "#1565c0", 55), ("baseline", "#c62828", 80)):
        pontos = " ".join(
            f"{60 + p['idade_dias'] / xmax * 620:.2f},{340 - p[metodo] / ymax * 300:.2f}"
            for p in curvas
        )
        partes.append(
            f'<polyline points="{pontos}" fill="none" stroke="{cor}" stroke-width="2"/>'
        )
        for p in curvas:
            partes.append(
                f'<circle cx="{60 + p["idade_dias"] / xmax * 620:.2f}" cy="{340 - p[metodo] / ymax * 300:.2f}" r="3" fill="{cor}"/>'
            )
        partes.append(f'<text x="550" y="{y}" fill="{cor}">{metodo}</text>')
    return "\n".join([*partes, "</svg>"])


def avaliar_teste(
    pasta_execucao: Path,
    reavaliar: bool = False,
    calibracao: Path = ARQUIVO_CALIBRACAO_PADRAO,
) -> Path:
    """Carrega o melhor checkpoint e grava JSON comparativo e gráfico SVG.

    Mantém o bloqueio de reavaliação; outra medição ganha arquivo próprio.
    Recusa metadados alterados desde o treino antes de abrir as imagens.
    """
    from training.treino.modelo import carregar_checkpoint

    pasta = Path(pasta_execucao)
    execucao = json.loads((pasta / "execucao.json").read_text("utf-8"))
    checkpoint = pasta / "melhor.pt"
    resumo = hash_arquivo(checkpoint)
    destino = pasta / f"avaliacao_teste_{resumo[:8]}.json"
    if destino.exists():
        if not reavaliar:
            raise FileExistsError("Teste já medido. Use --reavaliar para nova medição.")
        destino = destino.with_stem(f"{destino.stem}_{uuid4().hex}")
    info = ler_dataset(Path(execucao["dataset"]["caminho"]))
    if info.hash_metadados != execucao["dataset"]["hash_metadados_sha256"]:
        raise ValueError("Os metadados do dataset mudaram desde o treino.")
    problemas = verificar_estrutura(info)
    if problemas:
        raise ValueError(" ".join(problemas))
    semente = execucao["semente_global"]
    random.seed(semente)
    np.random.seed(semente)
    torch.manual_seed(semente)
    torch.use_deterministic_algorithms(True, warn_only=True)
    calibracao = Path(calibracao)
    dados_baseline = json.loads(calibracao.read_text("utf-8"))
    modelo, _ = carregar_checkpoint(checkpoint, "cpu")
    comparacao = comparar_modelo_baseline(modelo, info, dados_baseline["limiar_v"])
    bibliotecas = {"python": platform.python_version()}
    for nome in (
        "torch",
        "numpy",
        "Pillow",
        "opencv-python-headless",
        "segmentation-models-pytorch",
        "albumentations",
        "torchmetrics",
    ):
        try:
            bibliotecas[nome] = version(nome)
        except PackageNotFoundError:
            bibliotecas[nome] = None
    resultado = {
        "versao_relatorio": 1,
        "execucao": execucao["identificador"],
        "avaliado_em": datetime.now(timezone.utc).isoformat(),
        "checkpoint_sha256": resumo,
        "modelo_versao": execucao.get("modelo_versao"),
        "hash_metadados_sha256": info.hash_metadados,
        "semente_global": semente,
        "sementes_por_conjunto": info.sementes_por_conjunto(),
        "bibliotecas": bibliotecas,
        "dispositivo": "cpu",
        "baseline_calibracao": dados_baseline,
        "baseline_calibracao_sha256": hash_arquivo(calibracao),
        "amostras_teste": len(info.do_conjunto("teste")),
        "metricas": comparacao["modelo"],
        "comparacao": comparacao,
    }
    grafico = destino.with_suffix(".svg")
    grafico.write_text(
        grafico_idade_svg(comparacao["curvas_erro_por_idade"]), encoding="utf-8"
    )
    resultado["grafico_erro_idade"] = grafico.name
    with destino.open("x", encoding="utf-8") as arquivo:
        arquivo.write(
            json.dumps(
                resultado, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
            )
            + "\n"
        )
    return destino
