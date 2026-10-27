"""Mede critérios versionados do dataset de recomposição real v5."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from training.dataset_sintetico import (
    EROSAO_PLACA_PX,
    FAIXAS_COBERTURA_RECOMPOSICAO,
    NOMES_BASES_REAIS,
    TOLERANCIA_RECOMPOSICAO_PP,
    RecorteInsetoReal,
    _carregar_base_real,
    _carregar_recortes_coco,
    _colar_recorte_real,
    _criar_base_sintetica,
    _desenhar_distratores,
    _selecionar_distratores,
    _transformar_recorte_real,
)
from training.medicoes_recomposicao import medir_espalhamento
from training.treino.dados import (
    Amostra,
    ler_dataset,
    verificar_estrutura,
    verificar_mascaras,
)

REFERENCIAS_OCUPACAO = {"1-2%": 0.35, "2-4%": 0.57, "4-8%": 0.88}
REFERENCIA_AGLOMERACAO = 0.05
TOLERANCIA_OCUPACAO = 0.10
REFERENCIAS_COLAGEM = {300: 14.38, 900: 34.65}


def _aplicar_alpha(
    destino: np.ndarray,
    mascara_placa: np.ndarray,
    recorte: Image.Image,
    centro_x: int,
    centro_y: int,
) -> None:
    """Une alfa binária na placa sem extrapolar sua superfície."""
    alfa = np.asarray(recorte.getchannel("A"), dtype=np.uint8) > 0
    altura, largura = destino.shape
    x0 = centro_x - recorte.width // 2
    y0 = centro_y - recorte.height // 2
    x1, y1 = x0 + recorte.width, y0 + recorte.height
    px0, py0 = max(0, x0), max(0, y0)
    px1, py1 = min(largura, x1), min(altura, y1)
    if px1 <= px0 or py1 <= py0:
        return
    patch = alfa[py0 - y0 : py1 - y0, px0 - x0 : px1 - x0]
    destino[py0:py1, px0:px1] |= patch & mascara_placa[py0:py1, px0:px1]


def medir_calibracao_colagens(
    recortes: list[RecorteInsetoReal],
    area_placa_px: int,
    fator_escala: float,
    semente: int = 20261021,
    repeticoes: int = 20,
) -> dict[str, Any]:
    """Compara 300 e 900 colagens uniformes com as duas referências fixas."""
    if area_placa_px <= 0 or repeticoes < 1:
        raise ValueError(
            "A área da placa e o número de repetições devem ser positivos."
        )
    if len(recortes) * 2 < max(REFERENCIAS_COLAGEM):
        raise ValueError("A calibração exige pelo menos 450 recortes distintos.")
    largura = 768
    altura = 576
    proporcao = 450 / 220
    largura_placa = min(largura - 64, round(math.sqrt(area_placa_px * proporcao)))
    altura_placa = min(altura - 64, round(area_placa_px / largura_placa))
    area_placa = np.zeros((altura, largura), dtype=bool)
    x0, y0 = (largura - largura_placa) // 2, (altura - altura_placa) // 2
    area_placa[y0 : y0 + altura_placa, x0 : x0 + largura_placa] = True
    medidos = {quantidade: [] for quantidade in REFERENCIAS_COLAGEM}

    for repeticao in range(repeticoes):
        rng = random.Random(semente + repeticao)
        disponiveis = [indice for indice in range(len(recortes)) for _ in range(2)]
        rng.shuffle(disponiveis)
        coberta = np.zeros_like(area_placa)
        for indice_colagem, indice_recorte in enumerate(disponiveis[:900], start=1):
            transformado = _transformar_recorte_real(
                recortes[indice_recorte].imagem, rng, fator_escala
            )
            margem_x = max(1, transformado.width // 2)
            margem_y = max(1, transformado.height // 2)
            centro_x = rng.randint(x0 + margem_x, x0 + largura_placa - margem_x - 1)
            centro_y = rng.randint(y0 + margem_y, y0 + altura_placa - margem_y - 1)
            _aplicar_alpha(coberta, area_placa, transformado, centro_x, centro_y)
            transformado.close()
            if indice_colagem in medidos:
                medidos[indice_colagem].append(
                    100.0 * float(coberta.sum()) / float(area_placa.sum())
                )

    resumo = {}
    for quantidade, referencia in REFERENCIAS_COLAGEM.items():
        valores = medidos[quantidade]
        media = float(np.mean(valores))
        razao = media / referencia
        resumo[str(quantidade)] = {
            "colagens": quantidade,
            "cobertura_referencia_percentual": referencia,
            "cobertura_media_percentual": media,
            "desvio_padrao_percentual": float(np.std(valores, ddof=0)),
            "razao_referencia": razao,
            "aceita": 0.85 <= razao <= 1.15,
        }
    return {
        "versao": "colagens_uniformes_v1",
        "semente": semente,
        "repeticoes": repeticoes,
        "fator_escala_recorte": fator_escala,
        "area_placa_px": int(area_placa.sum()),
        "politica_reuso": "máximo de duas ocorrências por recorte em cada execução",
        "resultados": resumo,
        "aceita": all(item["aceita"] for item in resumo.values()),
    }


def medir_espalhamento_dataset(
    diretorio: Path,
    minimo_amostras: int = 100,
    diretorio_mascaras: Path | None = None,
    referencias_ocupacao: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Aplica o protocolo de cinza fixo, grade excluída e tiles de 24 px."""
    registros = []
    for caminho in sorted((diretorio / "imagens").glob("*.png")):
        mascara_path = (diretorio_mascaras or diretorio / "mascaras") / caminho.name
        with Image.open(caminho) as imagem_aberta:
            rgb = np.asarray(imagem_aberta.convert("RGB"), dtype=np.uint8)
        with Image.open(mascara_path) as mascara_aberta:
            mascara = np.asarray(mascara_aberta.convert("L"), dtype=np.uint8)
        registros.append(
            {
                "id": caminho.stem,
                "medida": medir_espalhamento(rgb, mascara, sem_grade=True),
            }
        )
    if not registros:
        raise ValueError("Não há imagens para medir o espalhamento.")
    faixas = {}
    referencias = referencias_ocupacao or REFERENCIAS_OCUPACAO
    for nome, referencia in referencias.items():
        minimo, maximo = map(float, nome.rstrip("%").split("-"))
        grupo = [
            item["medida"]
            for item in registros
            if minimo / 100 <= item["medida"]["fracao_escura"] < maximo / 100
        ]
        ocupacao = (
            float(np.mean([item["ocupacao"] for item in grupo])) if grupo else None
        )
        aglomeracao = (
            float(np.mean([item["aglomeracao"] for item in grupo])) if grupo else None
        )
        faixas[nome] = {
            "amostras": len(grupo),
            "ocupacao_media": ocupacao,
            "referencia_ocupacao": referencia,
            "diferenca_ocupacao": ocupacao - referencia
            if ocupacao is not None
            else None,
            "aglomeracao_media": aglomeracao,
            "limite_aglomeracao": REFERENCIA_AGLOMERACAO,
            "aceita": (
                ocupacao is not None
                and abs(ocupacao - referencia) <= TOLERANCIA_OCUPACAO
                and aglomeracao is not None
                and aglomeracao <= REFERENCIA_AGLOMERACAO
            ),
        }
    amostras_suficientes = len(registros) >= minimo_amostras
    faixas_aceitas = all(item["aceita"] for item in faixas.values())
    return {
        "versao": "espalhamento_recomposicao_v5",
        "amostras_medidas": len(registros),
        "minimo_amostras": minimo_amostras,
        "amostras_suficientes": amostras_suficientes,
        "faixas_aceitas": faixas_aceitas,
        "aceita": amostras_suficientes and faixas_aceitas,
        "criterio_cinza": "conversão RGB de ponto fixo, valor <110",
        "criterio_aglomeracao": "maior que 500 px após remover linhas retas de 41 px",
        "criterio_ocupacao": "tiles de 24 px com pelo menos 3 pixels escuros",
        "faixas": faixas,
        "resultados": registros,
    }


def calcular_correlacao_idade_cobertura(amostras: Sequence[Amostra]) -> float:
    """Calcula Pearson entre idade e cobertura de todas as amostras fornecidas."""
    if len(amostras) < 2:
        return 0.0
    return float(
        np.corrcoef(
            [amostra.idade_dias for amostra in amostras],
            [amostra.percentual_real for amostra in amostras],
        )[0, 1]
    )


def comparar_reprodutibilidade(
    primeira: Path, segunda: Path, quantidade: int = 100
) -> dict[str, Any]:
    """Compara SHA-256 de imagens, máscaras e metadados iniciais."""
    if quantidade < 1:
        raise ValueError("A quantidade de amostras precisa ser positiva.")
    registros = []
    for raiz in (primeira, segunda):
        registros.append(
            [
                json.loads(linha)
                for linha in (raiz / "metadados.jsonl").read_text("utf-8").splitlines()
                if linha.strip()
            ][:quantidade]
        )
    amostras = min(quantidade, *(len(registro) for registro in registros))
    comparados = iguais = 0
    diferencas = []
    for indice in range(amostras):
        identificador = f"amostra_{indice + 1:06d}"
        for pasta in ("imagens", "mascaras"):
            nome = f"{identificador}.png"
            comparados += 1
            digestos = [
                hashlib.sha256((raiz / pasta / nome).read_bytes()).hexdigest()
                for raiz in (primeira, segunda)
            ]
            if digestos[0] == digestos[1]:
                iguais += 1
            else:
                diferencas.append(f"{pasta}/{nome}")
        comparados += 1
        linhas = [
            json.dumps(registro[indice], sort_keys=True) for registro in registros
        ]
        if linhas[0] == linhas[1]:
            iguais += 1
        else:
            diferencas.append(f"metadados/{identificador}")
    return {
        "versao": "sha256_primeiras_amostras_v1",
        "quantidade_solicitada": quantidade,
        "amostras_comparadas": amostras,
        "arquivos_comparados": comparados,
        "arquivos_identicos": iguais,
        "diferencas": diferencas,
        "aceita": amostras == quantidade and not diferencas,
    }


def medir_trocar_contra_aleatoria(
    diretorio: Path,
    recortes: list[RecorteInsetoReal],
    placas_reais: Path,
    mascaras_bases: Path,
    maximo_amostras: int = 100,
) -> dict[str, Any]:
    """Compara densidade alta com colagem independente de centros uniformes."""
    import cv2

    raiz = diretorio.resolve()
    configuracao = json.loads((raiz / "configuracao.json").read_text("utf-8"))
    metadados = [
        json.loads(linha)
        for linha in (raiz / "metadados.jsonl").read_text("utf-8").splitlines()
        if linha.strip()
    ]
    if maximo_amostras < 1:
        raise ValueError("O máximo de amostras de comparação precisa ser positivo.")
    metadados = [
        registro
        for registro in metadados
        if registro["faixa_cobertura_alvo"] == "trocar"
    ][:maximo_amostras]
    recortes_por_id = {recorte.identificador: recorte for recorte in recortes}
    medidas = []
    for registro in metadados:
        ids_recortes = [str(valor) for valor in registro["recortes_coco_ids_usados"]]
        if not ids_recortes or any(
            nome not in recortes_por_id for nome in ids_recortes
        ):
            continue
        resolucao = tuple(int(v) for v in configuracao["resolucao"])
        if registro["origem_base"] == "real_ums":
            base = _carregar_base_real(
                placas_reais / "imagens" / f"{registro['placa_base_id']}.png",
                placas_reais,
                resolucao,
                mascaras_bases,
            )
            imagem_base, mascara_base = base.imagem, base.mascara
        else:
            rng_base = random.Random(int(registro["semente"]))
            imagem_base, mascara_base = _criar_base_sintetica(resolucao, rng_base)
            distratores = _selecionar_distratores(rng_base) or ["poeira"]
            import numpy as np

            ys, xs = np.nonzero(np.asarray(mascara_base) == 1)
            imagem_rgba = imagem_base.convert("RGBA")
            _desenhar_distratores(
                imagem_rgba,
                (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1),
                distratores,
                rng_base,
            )
            imagem_base = imagem_rgba.convert("RGB")

        import numpy as np

        imagem = np.asarray(imagem_base.convert("RGB"), dtype=np.uint8).copy()
        classes_base = np.asarray(mascara_base, dtype=np.uint8)
        placa = np.isin(classes_base, (1, 2))
        coberta = classes_base == 2
        altura, largura = classes_base.shape
        raio = max(1, round(EROSAO_PLACA_PX * largura / 768))
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (2 * raio + 1, 2 * raio + 1)
        )
        centros = np.argwhere(
            cv2.erode(placa.astype(np.uint8), kernel, iterations=1).astype(bool)
        )
        if not len(centros):
            continue
        rng = random.Random(int(registro["semente"]) ^ 0xA1EA700)
        area_placa = int(placa.sum())
        alvo = float(registro["percentual_cobertura_real"])
        melhor_diferenca = float("inf")
        melhor_imagem = imagem.copy()
        melhor_coberta = coberta.copy()
        melhor_percentual = 100.0 * int(coberta.sum()) / max(1, area_placa)
        for identificador in ids_recortes:
            recorte = _transformar_recorte_real(
                recortes_por_id[identificador].imagem,
                rng,
                float(configuracao["fator_escala_recorte"]),
            )
            y, x = centros[rng.randrange(len(centros))]
            _colar_recorte_real(
                imagem,
                coberta,
                placa,
                recorte,
                int(x),
                int(y),
            )
            recorte.close()
            percentual = 100.0 * int(coberta.sum()) / max(1, area_placa)
            diferenca = abs(percentual - alvo)
            if diferenca < melhor_diferenca:
                melhor_diferenca = diferenca
                melhor_imagem = imagem.copy()
                melhor_coberta = coberta.copy()
                melhor_percentual = percentual
            if diferenca <= TOLERANCIA_RECOMPOSICAO_PP:
                break
        mascara_uniforme = np.zeros_like(classes_base)
        mascara_uniforme[classes_base == 255] = 255
        mascara_uniforme[placa] = 1
        mascara_uniforme[melhor_coberta & placa] = 2
        with Image.open(raiz / "imagens" / f"{registro['id']}.png") as imagem_atual:
            atual_rgb = np.asarray(imagem_atual.convert("RGB"), dtype=np.uint8)
        with Image.open(raiz / "mascaras" / f"{registro['id']}.png") as mascara_atual:
            atual_mask = np.asarray(mascara_atual.convert("L"), dtype=np.uint8)
        medida_atual = medir_espalhamento(atual_rgb, atual_mask, sem_grade=True)
        medida_uniforme = medir_espalhamento(
            melhor_imagem, mascara_uniforme, sem_grade=True
        )
        medidas.append(
            {
                "id": registro["id"],
                "cobertura_real": float(registro["percentual_cobertura_real"]),
                "cobertura_uniforme": melhor_percentual,
                "diferenca_cobertura_pp": melhor_percentual
                - float(registro["percentual_cobertura_real"]),
                "aglomeracao_real": medida_atual["aglomeracao"],
                "aglomeracao_uniforme": medida_uniforme["aglomeracao"],
                "diferenca_aglomeracao": medida_atual["aglomeracao"]
                - medida_uniforme["aglomeracao"],
                "ocupacao_real": medida_atual["ocupacao"],
                "ocupacao_uniforme": medida_uniforme["ocupacao"],
                "diferenca_ocupacao": medida_atual["ocupacao"]
                - medida_uniforme["ocupacao"],
                "densidade_comparavel_1pp": melhor_diferenca <= 1.0,
            }
        )
    if not medidas:
        raise ValueError("Não há amostras trocar com recortes para comparar.")
    return {
        "versao": "trocar_centros_uniformes_v1",
        "amostras": len(medidas),
        "maximo_amostras": maximo_amostras,
        "amostras_com_densidade_comparavel_1pp": sum(
            item["densidade_comparavel_1pp"] for item in medidas
        ),
        "politica": "mesmos recortes por amostra, centros independentes uniformes na placa erodida, sem foco",
        "aglomeracao_real_media": float(
            np.mean([m["aglomeracao_real"] for m in medidas])
        ),
        "aglomeracao_uniforme_media": float(
            np.mean([m["aglomeracao_uniforme"] for m in medidas])
        ),
        "diferenca_aglomeracao_media": float(
            np.mean([m["diferenca_aglomeracao"] for m in medidas])
        ),
        "ocupacao_real_media": float(np.mean([m["ocupacao_real"] for m in medidas])),
        "ocupacao_uniforme_media": float(
            np.mean([m["ocupacao_uniforme"] for m in medidas])
        ),
        "diferenca_ocupacao_media": float(
            np.mean([m["diferenca_ocupacao"] for m in medidas])
        ),
        "resultados": medidas,
    }


def avaliar_dataset(
    diretorio: Path,
    calibracao_k: dict[str, Any] | None = None,
    reproducibilidade: dict[str, Any] | None = None,
    diretorio_espalhamento: Path | None = None,
    referencia_real: dict[str, Any] | None = None,
    comparacao_uniforme: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Mede integridade, divisão, rótulos, distratores, faixas e correlação."""
    info = ler_dataset(diretorio)
    metadados = [
        json.loads(linha)
        for linha in (info.raiz / "metadados.jsonl").read_text("utf-8").splitlines()
        if linha.strip()
    ]
    imagens = sorted((info.raiz / "imagens").glob("*.png"))
    ids = [amostra.identificador for amostra in info.amostras]
    sementes = [amostra.semente for amostra in info.amostras]
    divisao = {
        conjunto: info.do_conjunto(conjunto)
        for conjunto in ("treino", "validacao", "teste")
    }
    origens_por_conjunto = {
        nome: {
            origem
            for amostra in amostras
            for origem in (
                *amostra.placas_origem_recortes,
                *((amostra.placa_base_id,) if amostra.placa_base_id else ()),
            )
        }
        for nome, amostras in divisao.items()
    }
    cruzamentos = {
        f"{a}/{b}": sorted(origens_por_conjunto[a] & origens_por_conjunto[b])
        for a, b in (
            ("treino", "validacao"),
            ("treino", "teste"),
            ("validacao", "teste"),
        )
    }
    problemas = verificar_estrutura(info) + verificar_mascaras(info.amostras)
    dimensoes_validas = True
    for caminho in imagens:
        with Image.open(caminho) as imagem:
            dimensoes_validas &= imagem.size == (768, 576) and imagem.mode == "RGB"
    classes_validas = True
    cobertura_metadados = True
    for amostra in info.amostras:
        with Image.open(amostra.mascara) as mascara_aberta:
            mascara = np.asarray(mascara_aberta.convert("L"), dtype=np.uint8)
        classes_validas &= bool(np.isin(mascara, (0, 1, 2, 255)).all())
        contagem = np.bincount(mascara.ravel(), minlength=256)
        percentual = 100 * contagem[2] / max(1, contagem[1] + contagem[2])
        cobertura_metadados &= abs(percentual - amostra.percentual_real) <= 0.01
    distratores_sinteticos = [
        registro
        for registro in metadados
        if registro.get("origem_base") == "sintetica_stickfly_k45"
    ]
    distratores_presentes = all(
        registro.get("distratores_presentes") for registro in distratores_sinteticos
    )
    faixas = {}
    for nome, _, _ in FAIXAS_COBERTURA_RECOMPOSICAO:
        grupo = [r for r in metadados if r["faixa_cobertura_alvo"] == nome]
        atingidos = sum(bool(r["alvo_atingido"]) for r in grupo)
        faixas[nome] = {
            "amostras": len(grupo),
            "alvos_atingidos": atingidos,
            "taxa_alvo_atingido": atingidos / max(1, len(grupo)),
            "meta_atingimento": 0.9 if nome in ("ok", "atencao") else None,
            "aceita": (
                atingidos / max(1, len(grupo)) >= 0.9
                if nome in ("ok", "atencao")
                else True
            ),
        }
    referencias = {
        nome: float(dados["ocupacao_media"])
        for nome, dados in (referencia_real or {}).get("faixas", {}).items()
        if dados.get("ocupacao_media") is not None
    }
    espalhamento = medir_espalhamento_dataset(
        diretorio_espalhamento or info.raiz,
        referencias_ocupacao=referencias or None,
    )
    relatorio_geracao = json.loads(
        (info.raiz / "relatorio_geracao.json").read_text("utf-8")
    )
    ids_avaliacao = set(
        relatorio_geracao.get("separacao_placas", {}).get("avaliacao", [])
    )
    placas_usadas = set().union(*origens_por_conjunto.values())
    cruzamentos_avaliacao = sorted(ids_avaliacao & placas_usadas)
    bases_por_conjunto = {
        nome: sorted(
            {
                amostra.placa_base_id
                for amostra in amostras
                if amostra.placa_base_id is not None
            }
        )
        for nome, amostras in divisao.items()
    }
    faixas_por_conjunto = {
        nome: {
            faixa: sum(amostra.faixa == faixa for amostra in amostras)
            for faixa in ("ok", "atencao", "trocar")
        }
        for nome, amostras in divisao.items()
    }
    correlacao = calcular_correlacao_idade_cobertura(info.amostras)
    criterios = {
        "P_particao": {
            "cruzamentos_entre_conjuntos": cruzamentos,
            "sem_vazamento_entre_conjuntos": not any(cruzamentos.values()),
            "placas_avaliacao_usadas": cruzamentos_avaliacao,
            "zero_placas_avaliacao_usadas": not cruzamentos_avaliacao,
            "amostras_por_conjunto": {
                nome: len(amostras) for nome, amostras in divisao.items()
            },
            "origens_por_conjunto": {
                nome: sorted(origens) for nome, origens in origens_por_conjunto.items()
            },
            "bases_reais_por_conjunto": bases_por_conjunto,
            "bases_minimas_3_atendidas": all(
                len(bases) >= 3 for bases in bases_por_conjunto.values()
            ),
            "limite_diversidade": relatorio_geracao.get("diversidade_fundos"),
            "problemas_carregador": problemas,
            "aceita": (
                not any(cruzamentos.values())
                and not cruzamentos_avaliacao
                and not problemas
            ),
        },
        "L_rotulos": {
            "classes_validas": classes_validas,
            "cobertura_recalculada_confere": cobertura_metadados,
            "255_fora_do_numerador_e_denominador": True,
            "dimensoes_rgb_768x576": dimensoes_validas,
            "aceita": classes_validas and cobertura_metadados and dimensoes_validas,
        },
        "D_distratores": {
            "amostras_base_sintetica": len(distratores_sinteticos),
            "com_distrator": sum(
                bool(r.get("distratores_presentes")) for r in distratores_sinteticos
            ),
            "todas_com_distrator": distratores_presentes,
            "aceita": distratores_presentes,
        },
        "C_espalhamento": espalhamento,
        "T_alvo_por_faixa": {
            "faixas": faixas,
            "cobertura_real_maxima": max(
                (amostra.percentual_real for amostra in info.amostras), default=0.0
            ),
            "alvo_maximo_trocar": max(
                (
                    float(r["percentual_cobertura_alvo"])
                    for r in metadados
                    if r["faixa_cobertura_alvo"] == "trocar"
                ),
                default=0.0,
            ),
            "aceita": (
                all(dados["aceita"] for dados in faixas.values())
                and max(
                    (
                        float(r["percentual_cobertura_alvo"])
                        for r in metadados
                        if r["faixa_cobertura_alvo"] == "trocar"
                    ),
                    default=0.0,
                )
                <= max(
                    (amostra.percentual_real for amostra in info.amostras),
                    default=0.0,
                )
                + TOLERANCIA_RECOMPOSICAO_PP
            ),
        },
        "K_calibracao_colagens": {
            "medicao": calibracao_k,
            "aceita": calibracao_k is not None and bool(calibracao_k.get("aceita")),
        },
        "R_reprodutibilidade": {
            "medicao": reproducibilidade,
            "aceita": reproducibilidade is not None
            and bool(reproducibilidade.get("aceita")),
        },
        "I_integridade": {
            "ids_unicos": len(ids) == len(set(ids)),
            "sementes_unicas": len(sementes) == len(set(sementes)),
            "quantidade_imagens": len(imagens),
            "faixas_em_tercos": (
                max(
                    sum(r["faixa_cobertura_alvo"] == faixa for r in metadados)
                    for faixa in ("ok", "atencao", "trocar")
                )
                - min(
                    sum(r["faixa_cobertura_alvo"] == faixa for r in metadados)
                    for faixa in ("ok", "atencao", "trocar")
                )
                <= 1
            ),
            "faixas_por_conjunto": faixas_por_conjunto,
            "correlacao_idade_cobertura_global": correlacao,
            "correlacao_abaixo_limite": abs(correlacao) < 0.1,
            "aceita": (
                len(ids) == len(set(ids))
                and len(sementes) == len(set(sementes))
                and len(imagens) == len(info.amostras)
                and abs(correlacao) < 0.1
            ),
        },
    }
    criterios["C_espalhamento"]["aceita"] = espalhamento["aceita"]
    criterios["C_espalhamento"]["referencia_placas_reais"] = referencia_real
    criterios["C_espalhamento"]["trocar_contra_uniforme"] = comparacao_uniforme
    return {
        "versao": "avaliacao_recomposicao_v5",
        "amostras": len(info.amostras),
        "criterios": criterios,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--saida", type=Path, required=True)
    parser.add_argument(
        "--espalhamento",
        type=Path,
        help="Conjunto adicional com pelo menos 100 amostras para o critério C.",
    )
    parser.add_argument("--recortes-k", type=Path)
    parser.add_argument("--placas-reais", type=Path)
    parser.add_argument("--mascaras-bases", type=Path)
    parser.add_argument("--fator-escala", type=float, default=1.0)
    parser.add_argument("--repeticoes-k", type=int, default=20)
    parser.add_argument("--semente-k", type=int, default=20261021)
    parser.add_argument("--trocar-uniforme", action="store_true")
    parser.add_argument("--reprodutibilidade", nargs=2, type=Path)
    parser.add_argument("--placas-referencia", type=Path)
    parser.add_argument("--mascaras-referencia", type=Path)
    parser.add_argument("--atualizar-relatorio-geracao", action="store_true")
    args = parser.parse_args()
    calibracao_k = None
    recortes_carregados = None
    if args.recortes_k is not None:
        if args.placas_reais is None:
            parser.error("--recortes-k exige --placas-reais.")
        relatorio_execucao = json.loads(
            (args.dataset / "relatorio_geracao.json").read_text("utf-8")
        )
        nomes = set(
            relatorio_execucao.get("separacao_placas", {}).get("composicao", [])
        )
        recortes_carregados, _, _ = _carregar_recortes_coco(args.recortes_k, nomes)
        recortes = recortes_carregados
        elegiveis = {Path(nome).stem for nome in NOMES_BASES_REAIS}
        if args.mascaras_bases is not None:
            manifesto = json.loads(
                (args.mascaras_bases.parent / "configuracao.json").read_text("utf-8")
            )
            elegiveis = set(manifesto["bases_elegiveis"])
        areas = []
        for nome in sorted(elegiveis):
            caminho = (
                args.mascaras_bases / f"{nome}.png" if args.mascaras_bases else None
            )
            if caminho is None or not caminho.is_file():
                caminho = args.placas_reais / "mascaras" / f"{nome}.png"
            with Image.open(caminho) as mascara_aberta:
                mascara = np.asarray(mascara_aberta.convert("L"), dtype=np.uint8)
            area = int(np.isin(mascara, (1, 2)).sum())
            if area:
                areas.append(area)
        if not areas:
            parser.error("Não foi possível medir a área das bases elegíveis.")
        calibracao_k = medir_calibracao_colagens(
            recortes,
            area_placa_px=round(float(np.mean(areas))),
            fator_escala=args.fator_escala,
            semente=args.semente_k,
            repeticoes=args.repeticoes_k,
        )
    reproducibilidade = (
        comparar_reprodutibilidade(*args.reprodutibilidade)
        if args.reprodutibilidade
        else None
    )
    referencia_real = None
    comparacao_uniforme = None
    if (args.placas_referencia is None) != (args.mascaras_referencia is None):
        parser.error("--placas-referencia e --mascaras-referencia devem vir juntas.")
    if args.placas_referencia is not None:
        referencia_real = medir_espalhamento_dataset(
            args.placas_referencia,
            minimo_amostras=1,
            diretorio_mascaras=args.mascaras_referencia,
        )
    if args.trocar_uniforme:
        if (
            recortes_carregados is None
            or args.placas_reais is None
            or args.mascaras_bases is None
        ):
            parser.error(
                "--trocar-uniforme exige --recortes-k, --placas-reais e --mascaras-bases."
            )
        comparacao_uniforme = medir_trocar_contra_aleatoria(
            args.dataset,
            recortes_carregados,
            args.placas_reais,
            args.mascaras_bases,
        )
    resultado = avaliar_dataset(
        args.dataset,
        calibracao_k=calibracao_k,
        reproducibilidade=reproducibilidade,
        diretorio_espalhamento=args.espalhamento,
        referencia_real=referencia_real,
        comparacao_uniforme=comparacao_uniforme,
    )
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    temporario = args.saida.with_suffix(args.saida.suffix + ".part")
    temporario.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporario.replace(args.saida)
    if args.atualizar_relatorio_geracao:
        caminho_relatorio = args.dataset / "relatorio_geracao.json"
        relatorio = json.loads(caminho_relatorio.read_text("utf-8"))
        relatorio["auditoria_aceite_v5"] = resultado
        temporario_relatorio = caminho_relatorio.with_suffix(".json.part")
        temporario_relatorio.write_text(
            json.dumps(relatorio, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        temporario_relatorio.replace(caminho_relatorio)
    print(
        json.dumps(
            {"amostras": resultado["amostras"], "criterios": resultado["criterios"]},
            ensure_ascii=False,
        )
    )
