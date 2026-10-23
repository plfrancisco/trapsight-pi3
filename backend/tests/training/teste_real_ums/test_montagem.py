"""Testes puros do contrato de saída do conjunto de cartões reais UMS."""

from __future__ import annotations

import numpy as np
from PIL import Image

from training.teste_real_ums import (
    Caixa,
    _criar_mascara_classes,
    _preparar_saida,
    _resumo_areas,
    transformar_caixa_rotacao_90,
)


def test_caixa_coco_escala_e_gira_sem_distorcer() -> None:
    caixa = transformar_caixa_rotacao_90(
        (10, 20, 30, 15), largura_original=25, escala_x=0.25, escala_y=0.25
    )

    assert caixa == Caixa(5, 15, 9, 23)


def test_mascara_real_unifica_insetos_e_preserva_placa_limpa() -> None:
    inseto_a = np.zeros((8, 10), dtype=bool)
    inseto_b = np.zeros((8, 10), dtype=bool)
    inseto_a[2:5, 2:5] = True
    inseto_b[3:6, 4:7] = True

    mascara = _criar_mascara_classes((10, 8), Caixa(1, 1, 9, 7), [inseto_a, inseto_b])

    assert set(np.unique(mascara)) == {0, 1, 2}
    assert mascara[1, 1] == 1
    assert mascara[2, 2] == 2
    assert mascara[3, 4] == 2
    assert mascara[0, 0] == 0


def test_resumo_compara_soma_de_mascaras_com_soma_de_caixas() -> None:
    resumo = _resumo_areas([Caixa(0, 0, 10, 10), Caixa(0, 0, 5, 4)], [80, 18])

    assert resumo["soma_area_caixas_px"] == 120
    assert resumo["soma_area_mascaras_px"] == 98
    assert resumo["diferenca_area_px"] == -22
    assert resumo["diferenca_relativa_percentual"] == -22 / 120 * 100


def test_saida_tem_dimensoes_de_modelo_sem_alterar_as_classes() -> None:
    imagem = Image.new("RGB", (200, 100), (240, 230, 220))
    mascara = np.ones((100, 200), dtype=np.uint8)
    mascara[30:50, 60:90] = 2

    imagem_final, mascara_final, escala = _preparar_saida(imagem, mascara)

    assert imagem_final.size == (768, 576)
    assert mascara_final.size == (768, 576)
    assert escala == 3.84
    assert set(np.unique(np.asarray(mascara_final))) == {0, 1, 2}
