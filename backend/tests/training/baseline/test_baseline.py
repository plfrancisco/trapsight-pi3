"""Testa calibração, percentual e limitação por sujeira do baseline."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from training.baseline import avaliar, calibrar, segmentar


def _gravar_amostra(
    raiz: Path,
    identificador: str,
    conjunto: str,
    imagem: np.ndarray,
    mascara: np.ndarray,
    semente: int,
) -> dict[str, object]:
    Image.fromarray(imagem).save(raiz / "imagens" / f"{identificador}.png")
    Image.fromarray(mascara).save(raiz / "mascaras" / f"{identificador}.png")
    registro: dict[str, object] = {
        "id": identificador,
        "semente": semente,
        "conjunto": conjunto,
        "percentual_cobertura_real": float(np.count_nonzero(mascara == 2))
        * 100.0
        / float(np.count_nonzero(mascara != 0)),
        "origem_base": "real_ums" if conjunto == "teste" else "sintetica_fixture",
    }
    return registro


def _criar_dataset(raiz: Path) -> None:
    (raiz / "imagens").mkdir(parents=True)
    (raiz / "mascaras").mkdir()
    (raiz / "configuracao.json").write_text(
        json.dumps({"semente_global": 20261021}),
        encoding="utf-8",
    )

    imagem_treino = np.full((4, 4, 3), 230, dtype=np.uint8)
    imagem_treino[0, 0] = 50
    mascara_treino = np.ones((4, 4), dtype=np.uint8)
    mascara_treino[0, 0] = 2
    treino = _gravar_amostra(
        raiz,
        "amostra_000001",
        "treino",
        imagem_treino,
        mascara_treino,
        101,
    )

    imagem_teste = np.full((10, 10, 3), 230, dtype=np.uint8)
    imagem_teste[0, 0] = 50
    imagem_teste[0, 1] = 20
    mascara_teste = np.ones((10, 10), dtype=np.uint8)
    mascara_teste[0, 0] = 2
    teste = _gravar_amostra(
        raiz,
        "amostra_000002",
        "teste",
        imagem_teste,
        mascara_teste,
        202,
    )

    (raiz / "metadados.jsonl").write_text(
        "".join(
            json.dumps(registro, sort_keys=True) + "\n" for registro in (treino, teste)
        ),
        encoding="utf-8",
    )


def test_calibracao_e_deterministica_para_a_mesma_semente(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    _criar_dataset(dataset)

    primeira = calibrar(dataset, tmp_path / "primeira.json")
    segunda = calibrar(dataset, tmp_path / "segunda.json")

    assert primeira == segunda
    assert primeira["limiar_v"] == 51
    assert 0 <= primeira["limiar_v"] <= 255
    assert primeira["semente_global"] == 20261021
    assert primeira["hash_conjunto_treino_sha256"]
    assert (tmp_path / "primeira.json").read_text(encoding="utf-8") == (
        tmp_path / "segunda.json"
    ).read_text(encoding="utf-8")


def test_calibracao_nao_usa_imagens_de_validacao_ou_teste(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    _criar_dataset(dataset)

    calibracao_original = calibrar(dataset, tmp_path / "original.json")
    imagem_teste = np.zeros((3, 3, 3), dtype=np.uint8)
    Image.fromarray(imagem_teste).save(dataset / "imagens" / "amostra_000002.png")
    calibracao_apos_alteracao = calibrar(dataset, tmp_path / "alterada.json")

    assert calibracao_apos_alteracao == calibracao_original


def test_percentual_corresponde_aos_pixels_binarios_da_mascara() -> None:
    imagem = np.full((4, 4, 3), 230, dtype=np.uint8)
    imagem[0, 0] = 50
    imagem[0, 1] = 20
    placa = np.ones((4, 4), dtype=bool)

    mascara_predita, percentual = segmentar(imagem, 51, placa)

    assert set(np.unique(mascara_predita)) <= {0, 255}
    assert int(np.count_nonzero(mascara_predita)) == 2
    assert percentual == round(2 * 100.0 / int(np.count_nonzero(placa)), 2)


def test_sujeira_escura_e_contada_como_cobertura_pelo_limiar_global(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "dataset"
    arquivo_calibracao = tmp_path / "baseline_calibracao.json"
    _criar_dataset(dataset)
    calibracao = calibrar(dataset, arquivo_calibracao)

    metricas = avaliar(
        dataset,
        "teste",
        arquivo_calibracao,
        tmp_path / "metricas.json",
    )

    assert metricas["metricas"]["dice_placa_coberta"] == 0.66666667
    assert metricas["metricas"]["iou_placa_coberta"] == 0.5
    assert calibracao["limiar_v"] == 51
    assert calibracao["dice_treino"] == 1.0
    assert metricas["metricas"]["erro_percentual_absoluto_medio_pp"] == 1.0
    assert metricas["metricas"]["acuracia_status"] == 1.0
    assert metricas["metricas_por_origem_base"]["real_ums"]["quantidade_amostras"] == 1
    assert (tmp_path / "metricas.json").is_file()


def test_calibracao_ignora_pixels_255_nos_histogramas(tmp_path: Path) -> None:
    dataset_255 = tmp_path / "dataset_255"
    dataset_zero = tmp_path / "dataset_zero"
    _criar_dataset(dataset_255)
    _criar_dataset(dataset_zero)

    imagem_255_path = dataset_255 / "imagens" / "amostra_000001.png"
    imagem_255 = np.asarray(Image.open(imagem_255_path).convert("RGB")).copy()
    imagem_255[0, 1] = 40
    Image.fromarray(imagem_255).save(imagem_255_path)
    mascara_255_path = dataset_255 / "mascaras" / "amostra_000001.png"
    mascara_255 = np.asarray(Image.open(mascara_255_path).convert("L")).copy()
    mascara_255[0, 1] = 255
    Image.fromarray(mascara_255).save(mascara_255_path)

    imagem_zero_path = dataset_zero / "imagens" / "amostra_000001.png"
    imagem_zero = np.asarray(Image.open(imagem_zero_path).convert("RGB")).copy()
    imagem_zero[0, 1] = 40
    Image.fromarray(imagem_zero).save(imagem_zero_path)
    mascara_zero_path = dataset_zero / "mascaras" / "amostra_000001.png"
    mascara_zero = np.asarray(Image.open(mascara_zero_path).convert("L")).copy()
    mascara_zero[0, 1] = 0
    Image.fromarray(mascara_zero).save(mascara_zero_path)

    calibracao_255 = calibrar(dataset_255, tmp_path / "calibracao_255.json")
    calibracao_zero = calibrar(dataset_zero, tmp_path / "calibracao_zero.json")

    assert calibracao_255["limiar_v"] == calibracao_zero["limiar_v"] == 51
    assert calibracao_255["dice_treino"] == calibracao_zero["dice_treino"] == 1.0


def test_avaliacao_ignora_255_no_segmento_e_denominador(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    arquivo_calibracao = tmp_path / "baseline_calibracao.json"
    _criar_dataset(dataset)
    calibrar(dataset, arquivo_calibracao)

    caminho_mascara = dataset / "mascaras" / "amostra_000002.png"
    mascara = np.asarray(Image.open(caminho_mascara).convert("L")).copy()
    mascara[0, 1] = 255
    Image.fromarray(mascara).save(caminho_mascara)

    metricas = avaliar(dataset, "teste", arquivo_calibracao)

    assert metricas["metricas"] == {
        "dice_placa_coberta": 1.0,
        "iou_placa_coberta": 1.0,
        "erro_percentual_absoluto_medio_pp": 0.0,
        "acuracia_status": 1.0,
    }
    assert (
        metricas["metricas_por_origem_base"]["real_ums"]["metricas"]
        == metricas["metricas"]
    )


def test_avaliacao_rejeita_classe_de_mascara_desconhecida(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    arquivo_calibracao = tmp_path / "baseline_calibracao.json"
    _criar_dataset(dataset)
    calibrar(dataset, arquivo_calibracao)

    caminho_mascara = dataset / "mascaras" / "amostra_000002.png"
    mascara = np.asarray(Image.open(caminho_mascara).convert("L")).copy()
    mascara[0, 1] = 3
    Image.fromarray(mascara).save(caminho_mascara)

    with pytest.raises(ValueError, match="classe não reconhecida"):
        avaliar(dataset, "teste", arquivo_calibracao)


def test_avaliacao_exige_pixels_de_placa_entre_as_classes_validas(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "dataset"
    arquivo_calibracao = tmp_path / "baseline_calibracao.json"
    _criar_dataset(dataset)
    calibrar(dataset, arquivo_calibracao)

    caminho_mascara = dataset / "mascaras" / "amostra_000002.png"
    Image.fromarray(np.full((10, 10), 255, dtype=np.uint8)).save(caminho_mascara)

    with pytest.raises(ValueError, match="sem pixels de placa"):
        avaliar(dataset, "teste", arquivo_calibracao)
