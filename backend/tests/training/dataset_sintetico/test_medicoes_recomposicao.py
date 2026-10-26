"""A grade não pode inflar a medida dos insetos e sujeira."""

import numpy as np
import pytest
from PIL import Image

from training.medicoes_recomposicao import (
    cinza_fixo,
    linhas_longas,
    medir_dataset,
    medir_espalhamento,
)


def test_cinza_em_ponto_fixo_e_fronteira_estrita():
    rgb = np.array([[[255, 0, 0], [0, 255, 0], [0, 0, 255]]], dtype=np.uint8)
    assert cinza_fixo(rgb).tolist() == [[76, 150, 29]]


def test_linhas_longas_remove_so_segmentos_retos_contiguos():
    a = np.zeros((100, 100), dtype=bool)
    a[20, 5:46] = True
    a[30, 5:45] = True
    a[10:70, 80] = True
    linhas = linhas_longas(a)
    assert linhas[20, 5:46].all()
    assert not linhas[30, 5:45].any()
    assert linhas[10:70, 80].all()


def test_grade_sai_da_aglomeracao_e_255_sai_das_areas():
    rgb = np.full((96, 96, 3), 230, dtype=np.uint8)
    rgb[45:49] = 0
    rgb[:, 45:49] = 0
    rgb[10:12, 10:12] = 20
    mascara = np.ones((96, 96), dtype=np.uint8)
    com = medir_espalhamento(rgb, mascara, False)
    sem = medir_espalhamento(rgb, mascara)
    assert com["aglomeracao"] > 0.9
    assert sem["aglomeracao"] == 0
    assert sem["pixels_escuros"] == 4
    assert sem["ocupacao"] == pytest.approx(1 / 16)
    mascara[10:12, 10:12] = 255
    ignorada = medir_espalhamento(rgb, mascara)
    assert ignorada["pixels_escuros"] == 0
    assert ignorada["pixels_placa"] == 96**2 - 4


def test_dataset_mede_pares_e_recusa_classes_invalidas(tmp_path):
    (tmp_path / "imagens").mkdir()
    (tmp_path / "mascaras").mkdir()
    imagem = np.full((48, 48, 3), 230, np.uint8)
    imagem[1:3, 1:3] = 20
    mascara = np.ones((48, 48), np.uint8)
    Image.fromarray(imagem).save(tmp_path / "imagens" / "a.png")
    Image.fromarray(mascara).save(tmp_path / "mascaras" / "a.png")
    medidas = medir_dataset(tmp_path)
    assert medidas["placas"] == 1
    assert medidas["registros"][0]["sem_grade"]["ocupacao"] == 0.25
    mascara[0, 0] = 3
    Image.fromarray(mascara).save(tmp_path / "mascaras" / "a.png")
    with pytest.raises(ValueError, match="Par inválido"):
        medir_dataset(tmp_path)
