"""Calibra e avalia o baseline de luminosidade com limiar HSV global."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError

VERSAO_CALIBRACAO = 1
LIMIAR_V_MINIMO = 0
LIMIAR_V_MAXIMO = 255
LIMIAR_ATENCAO = 40.0
LIMIAR_TROCAR = 70.0
DIVISOES_VALIDAS = {"treino", "validacao", "teste"}
ARQUIVO_CALIBRACAO_PADRAO = Path(__file__).with_name("baseline_calibracao.json")


@dataclass(frozen=True)
class RegistroAmostra:
    """Arquivos de imagem e máscara associados a uma amostra do dataset."""

    identificador: str
    semente: int
    conjunto: str
    imagem: Path
    mascara: Path


def _ler_dataset(diretorio: Path) -> tuple[int, list[RegistroAmostra]]:
    raiz = diretorio.resolve()
    caminho_configuracao = raiz / "configuracao.json"
    caminho_metadados = raiz / "metadados.jsonl"
    try:
        configuracao = json.loads(caminho_configuracao.read_text(encoding="utf-8"))
    except FileNotFoundError as erro:
        raise ValueError(f"Arquivo obrigatório ausente: {erro.filename}.") from erro
    except json.JSONDecodeError as erro:
        raise ValueError("configuracao.json precisa conter JSON válido.") from erro

    if not isinstance(configuracao, dict):
        raise ValueError("configuracao.json precisa conter um objeto JSON.")
    semente_global = configuracao.get("semente_global")
    if isinstance(semente_global, bool) or not isinstance(semente_global, int):
        raise ValueError("configuracao.json precisa registrar semente_global inteira.")

    try:
        linhas = caminho_metadados.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as erro:
        raise ValueError(f"Arquivo obrigatório ausente: {erro.filename}.") from erro

    registros: list[RegistroAmostra] = []
    identificadores: set[str] = set()
    for numero_linha, linha in enumerate(linhas, start=1):
        if not linha.strip():
            continue
        try:
            dados = json.loads(linha)
        except json.JSONDecodeError as erro:
            raise ValueError(
                f"metadados.jsonl contém JSON inválido na linha {numero_linha}."
            ) from erro
        if not isinstance(dados, dict):
            raise ValueError(
                f"A linha {numero_linha} dos metadados precisa ser objeto."
            )

        identificador = dados.get("id")
        semente = dados.get("semente")
        conjunto = dados.get("conjunto")
        if (
            not isinstance(identificador, str)
            or not identificador
            or Path(identificador).name != identificador
            or "/" in identificador
            or "\\" in identificador
        ):
            raise ValueError(f"Identificador inválido na linha {numero_linha}.")
        if identificador in identificadores:
            raise ValueError(f"Identificador duplicado nos metadados: {identificador}.")
        if isinstance(semente, bool) or not isinstance(semente, int):
            raise ValueError(
                f"A linha {numero_linha} precisa registrar uma semente inteira."
            )
        if not isinstance(conjunto, str) or conjunto not in DIVISOES_VALIDAS:
            raise ValueError(f"Divisão inválida na linha {numero_linha}.")

        identificadores.add(identificador)
        registros.append(
            RegistroAmostra(
                identificador=identificador,
                semente=semente,
                conjunto=conjunto,
                imagem=raiz / "imagens" / f"{identificador}.png",
                mascara=raiz / "mascaras" / f"{identificador}.png",
            )
        )

    if not registros:
        raise ValueError("metadados.jsonl não contém amostras.")
    return semente_global, registros


def _ler_par_imagem(registro: RegistroAmostra) -> tuple[np.ndarray, np.ndarray]:
    try:
        with Image.open(registro.imagem) as imagem_aberta:
            imagem = np.asarray(imagem_aberta.convert("RGB"), dtype=np.uint8)
        with Image.open(registro.mascara) as mascara_aberta:
            mascara = np.asarray(mascara_aberta.convert("L"), dtype=np.uint8)
    except FileNotFoundError as erro:
        raise ValueError(
            f"Imagem ou máscara ausente para {registro.identificador}."
        ) from erro
    except (OSError, UnidentifiedImageError) as erro:
        raise ValueError(
            f"Imagem ou máscara inválida para {registro.identificador}."
        ) from erro

    if imagem.shape[:2] != mascara.shape:
        raise ValueError(
            f"Imagem e máscara têm dimensões diferentes: {registro.identificador}."
        )
    if not np.isin(mascara, (0, 1, 2)).all():
        raise ValueError(
            f"Máscara contém classe não reconhecida: {registro.identificador}."
        )
    if not np.any(mascara != 0):
        raise ValueError(f"Máscara sem pixels de placa: {registro.identificador}.")
    return imagem, mascara


def segmentar(
    imagem_rgb: np.ndarray,
    limiar_v: int,
    mascara_placa: np.ndarray,
) -> tuple[np.ndarray, float]:
    """Marca pixels escuros dentro da placa e calcula o percentual coberto.

    `mascara_placa` representa o recorte da placa pressuposto pelo baseline.
    O limiar global é aplicado sem adaptação por imagem.
    """
    if isinstance(limiar_v, bool) or not isinstance(limiar_v, int):
        raise ValueError("O limiar V precisa ser inteiro.")
    if not LIMIAR_V_MINIMO <= limiar_v <= LIMIAR_V_MAXIMO:
        raise ValueError("O limiar V precisa estar entre 0 e 255.")
    imagem = np.asarray(imagem_rgb)
    placa = np.asarray(mascara_placa, dtype=bool)
    if imagem.dtype != np.uint8 or imagem.ndim != 3 or imagem.shape[2] != 3:
        raise ValueError("A imagem precisa ser RGB de 8 bits por canal.")
    if imagem.shape[:2] != placa.shape:
        raise ValueError("A imagem e a máscara da placa precisam ter o mesmo tamanho.")
    area_placa = int(np.count_nonzero(placa))
    if area_placa == 0:
        raise ValueError("A máscara não contém pixels da placa adesiva.")

    hsv = cv2.cvtColor(np.ascontiguousarray(imagem), cv2.COLOR_RGB2HSV)
    coberta = (hsv[:, :, 2] < limiar_v) & placa
    percentual = round(float(np.count_nonzero(coberta)) * 100.0 / area_placa, 2)
    return coberta.astype(np.uint8) * 255, percentual


def _hash_arquivo(caminho: Path) -> str:
    digest = hashlib.sha256()
    try:
        with caminho.open("rb") as arquivo:
            for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
                digest.update(bloco)
    except FileNotFoundError as erro:
        raise ValueError(
            f"Arquivo do conjunto de treino ausente: {caminho.name}."
        ) from erro
    return digest.hexdigest()


def _hash_conjunto_treino(
    semente_global: int,
    registros_treino: list[RegistroAmostra],
) -> str:
    if not registros_treino:
        raise ValueError("O dataset não contém amostras no conjunto treino.")
    digest = hashlib.sha256()
    cabecalho = json.dumps(
        {"semente_global": semente_global, "versao_hash": 1},
        sort_keys=True,
        separators=(",", ":"),
    )
    digest.update(cabecalho.encode("utf-8"))
    for registro in sorted(registros_treino, key=lambda amostra: amostra.identificador):
        proveniencia = {
            "id": registro.identificador,
            "semente": registro.semente,
            "imagem_sha256": _hash_arquivo(registro.imagem),
            "mascara_sha256": _hash_arquivo(registro.mascara),
        }
        digest.update(
            json.dumps(
                proveniencia,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
    return digest.hexdigest()


def _dice(tp: int, fp: int, fn: int) -> float:
    denominador = 2 * tp + fp + fn
    return 1.0 if denominador == 0 else 2.0 * tp / denominador


def _selecionar_limiar(
    positivos_por_valor: np.ndarray,
    limpos_por_valor: np.ndarray,
) -> tuple[int, float]:
    positivos_ate_limiar = np.concatenate(
        (np.zeros(1, dtype=np.int64), np.cumsum(positivos_por_valor, dtype=np.int64))
    )
    limpos_ate_limiar = np.concatenate(
        (np.zeros(1, dtype=np.int64), np.cumsum(limpos_por_valor, dtype=np.int64))
    )
    total_positivos = int(positivos_por_valor.sum())
    candidatos = range(LIMIAR_V_MINIMO, LIMIAR_V_MAXIMO + 1)
    resultados = [
        (
            _dice(
                int(positivos_ate_limiar[limiar]),
                int(limpos_ate_limiar[limiar]),
                total_positivos - int(positivos_ate_limiar[limiar]),
            ),
            -limiar,
        )
        for limiar in candidatos
    ]
    indice = max(range(len(resultados)), key=resultados.__getitem__)
    return indice, resultados[indice][0]


def _gravar_json(caminho: Path, dados: dict[str, Any]) -> None:
    caminho = caminho.resolve()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_name(f".{caminho.name}.tmp")
    try:
        temporario.write_text(
            json.dumps(dados, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        temporario.replace(caminho)
    finally:
        temporario.unlink(missing_ok=True)


def calibrar(
    diretorio_dataset: Path,
    arquivo_calibracao: Path = ARQUIVO_CALIBRACAO_PADRAO,
) -> dict[str, Any]:
    """Seleciona o limiar global por Dice no conjunto de treino e grava a calibração."""
    semente_global, registros = _ler_dataset(diretorio_dataset)
    registros_treino = [
        registro for registro in registros if registro.conjunto == "treino"
    ]
    if not registros_treino:
        raise ValueError("O dataset não contém amostras no conjunto treino.")

    positivos_por_valor = np.zeros(256, dtype=np.int64)
    limpos_por_valor = np.zeros(256, dtype=np.int64)
    for registro in registros_treino:
        imagem, mascara = _ler_par_imagem(registro)
        placa = mascara != 0
        valor = cv2.cvtColor(np.ascontiguousarray(imagem), cv2.COLOR_RGB2HSV)[:, :, 2]
        positivos_por_valor += np.bincount(valor[placa & (mascara == 2)], minlength=256)
        limpos_por_valor += np.bincount(valor[placa & (mascara == 1)], minlength=256)

    limiar_v, dice_treino = _selecionar_limiar(
        positivos_por_valor,
        limpos_por_valor,
    )
    calibracao = {
        "versao": VERSAO_CALIBRACAO,
        "metodo": "limiar_global_hsv_v",
        "regra": "V < limiar_v dentro da placa",
        "limiar_v": limiar_v,
        "dice_treino": round(dice_treino, 8),
        "semente_global": semente_global,
        "quantidade_amostras_treino": len(registros_treino),
        "hash_conjunto_treino_sha256": _hash_conjunto_treino(
            semente_global,
            registros_treino,
        ),
    }
    _gravar_json(arquivo_calibracao, calibracao)
    return calibracao


def _ler_calibracao(
    caminho: Path, semente_global: int, hash_treino: str
) -> dict[str, Any]:
    try:
        calibracao = json.loads(caminho.read_text(encoding="utf-8"))
    except FileNotFoundError as erro:
        raise ValueError(f"Arquivo de calibração ausente: {caminho}.") from erro
    except json.JSONDecodeError as erro:
        raise ValueError(
            "O arquivo de calibração precisa conter JSON válido."
        ) from erro
    if (
        not isinstance(calibracao, dict)
        or isinstance(calibracao.get("versao"), bool)
        or calibracao.get("versao") != VERSAO_CALIBRACAO
        or calibracao.get("metodo") != "limiar_global_hsv_v"
    ):
        raise ValueError("Versão de calibração ausente ou incompatível.")
    limiar_v = calibracao.get("limiar_v")
    if (
        isinstance(limiar_v, bool)
        or not isinstance(limiar_v, int)
        or not LIMIAR_V_MINIMO <= limiar_v <= LIMIAR_V_MAXIMO
    ):
        raise ValueError("A calibração registra um limiar V inválido.")
    semente_calibracao = calibracao.get("semente_global")
    if (
        isinstance(semente_calibracao, bool)
        or not isinstance(semente_calibracao, int)
        or semente_calibracao != semente_global
    ):
        raise ValueError("A semente da calibração não corresponde ao dataset.")
    if calibracao.get("hash_conjunto_treino_sha256") != hash_treino:
        raise ValueError("O conjunto de treino mudou desde a calibração.")
    return calibracao


def _derivar_status(percentual: float) -> str:
    if percentual < LIMIAR_ATENCAO:
        return "ok"
    if percentual <= LIMIAR_TROCAR:
        return "atencao"
    return "trocar"


def avaliar(
    diretorio_dataset: Path,
    split: str,
    arquivo_calibracao: Path = ARQUIVO_CALIBRACAO_PADRAO,
    arquivo_saida: Path | None = None,
) -> dict[str, Any]:
    """Calcula métricas do baseline usando um limiar já calibrado em treino."""
    if split not in DIVISOES_VALIDAS:
        raise ValueError("split precisa ser treino, validacao ou teste.")
    semente_global, registros = _ler_dataset(diretorio_dataset)
    registros_treino = [
        registro for registro in registros if registro.conjunto == "treino"
    ]
    hash_treino = _hash_conjunto_treino(semente_global, registros_treino)
    calibracao = _ler_calibracao(arquivo_calibracao, semente_global, hash_treino)
    registros_avaliados = [
        registro for registro in registros if registro.conjunto == split
    ]
    if not registros_avaliados:
        raise ValueError(f"O dataset não contém amostras no conjunto {split}.")

    tp = fp = fn = 0
    soma_erro_percentual = 0.0
    acertos_status = 0
    for registro in registros_avaliados:
        imagem, mascara = _ler_par_imagem(registro)
        placa = mascara != 0
        predicao, percentual_predito = segmentar(
            imagem,
            calibracao["limiar_v"],
            placa,
        )
        coberta_predita = predicao != 0
        coberta_real = mascara == 2
        percentual_real = round(
            float(np.count_nonzero(coberta_real))
            * 100.0
            / int(np.count_nonzero(placa)),
            2,
        )
        tp += int(np.count_nonzero(coberta_predita & coberta_real))
        fp += int(np.count_nonzero(coberta_predita & (mascara == 1)))
        fn += int(np.count_nonzero(~coberta_predita & coberta_real))
        soma_erro_percentual += abs(percentual_predito - percentual_real)
        acertos_status += int(
            _derivar_status(percentual_predito) == _derivar_status(percentual_real)
        )

    uniao = tp + fp + fn
    quantidade = len(registros_avaliados)
    relatorio = {
        "versao": 1,
        "metodo": "limiar_global_hsv_v",
        "conjunto": split,
        "quantidade_amostras": quantidade,
        "calibracao": {
            "limiar_v": calibracao["limiar_v"],
            "semente_global": calibracao["semente_global"],
            "hash_conjunto_treino_sha256": hash_treino,
        },
        "metricas": {
            "dice_placa_coberta": round(_dice(tp, fp, fn), 8),
            "iou_placa_coberta": round(1.0 if uniao == 0 else tp / uniao, 8),
            "erro_percentual_absoluto_medio_pp": round(
                soma_erro_percentual / quantidade,
                8,
            ),
            "acuracia_status": round(acertos_status / quantidade, 8),
        },
    }
    destino = arquivo_saida or diretorio_dataset / f"metricas_baseline_{split}.json"
    _gravar_json(destino, relatorio)
    return relatorio


def _criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calibra e avalia o baseline OpenCV por luminosidade."
    )
    subparsers = parser.add_subparsers(dest="comando", required=True)

    parser_calibrar = subparsers.add_parser(
        "calibrar",
        help="Escolhe o limiar V pelo Dice no conjunto de treino.",
    )
    parser_calibrar.add_argument("--dataset", type=Path, required=True)
    parser_calibrar.add_argument(
        "--calibracao",
        type=Path,
        default=ARQUIVO_CALIBRACAO_PADRAO,
        help="Arquivo JSON versionado que receberá o limiar e a proveniência.",
    )

    parser_avaliar = subparsers.add_parser(
        "avaliar",
        help="Avalia o limiar calibrado em uma divisão do dataset.",
    )
    parser_avaliar.add_argument("--dataset", type=Path, required=True)
    parser_avaliar.add_argument(
        "--split",
        choices=sorted(DIVISOES_VALIDAS),
        required=True,
    )
    parser_avaliar.add_argument(
        "--calibracao",
        type=Path,
        default=ARQUIVO_CALIBRACAO_PADRAO,
    )
    parser_avaliar.add_argument(
        "--saida",
        type=Path,
        help="Caminho do JSON de métricas; por padrão, fica no diretório do dataset.",
    )
    return parser


def main(argumentos: list[str] | None = None) -> int:
    """Executa os subcomandos e imprime o resultado em JSON."""
    parser = _criar_parser()
    opcoes = parser.parse_args(argumentos)
    try:
        if opcoes.comando == "calibrar":
            resultado = calibrar(opcoes.dataset, opcoes.calibracao)
        else:
            resultado = avaliar(
                opcoes.dataset,
                opcoes.split,
                opcoes.calibracao,
                opcoes.saida,
            )
    except (OSError, ValueError, cv2.error) as erro:
        parser.error(str(erro))
        return 2
    print(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
