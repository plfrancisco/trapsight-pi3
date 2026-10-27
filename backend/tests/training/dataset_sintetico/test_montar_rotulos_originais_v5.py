"""Confere prioridade entre SAM, sujeira, regiões ignoradas e placa limpa."""

import numpy as np
import pytest

from training.montar_rotulos_originais_v5 import aplicar_politica


@pytest.mark.parametrize("p_maior_que_limite", [True, False])
def test_base_aplica_decisoes_humanas_semanticas(p_maior_que_limite):
    placa = np.ones((12, 12), dtype=bool)
    mascara = np.ones((12, 12), dtype=np.uint8)
    mascara[0, 0] = 2
    labels = np.zeros((12, 12), dtype=np.int32)
    labels[1:3, 1:3] = 1
    labels[3:5, 3:5] = 2
    labels[5:7, 5:7] = 3
    regioes = [
        {"id": 1, "decisao": "sujeira", "evidencia": {"coco": []}},
        {"id": 2, "decisao": "inseto", "evidencia": {"coco": []}},
        {"id": 3, "decisao": "ambigua", "evidencia": {"coco": []}},
    ]

    resultado = aplicar_politica(
        mascara,
        placa,
        regioes,
        labels,
        np.zeros_like(placa),
        p_maior_que_limite=p_maior_que_limite,
        origem_base=True,
    )

    assert np.all(resultado[1:3, 1:3] == 1)
    assert np.all(resultado[3:5, 3:5] == 2)
    assert np.all(resultado[5:7, 5:7] == 255)
    assert resultado[0, 0] == 2
    assert set(np.unique(resultado)) == {1, 2, 255}


def test_p_baixo_classifica_regiao_sem_decisao_como_sujeira():
    placa = np.ones((8, 8), dtype=bool)
    mascara = np.ones((8, 8), dtype=np.uint8)
    labels = np.zeros((8, 8), dtype=np.int32)
    labels[2:4, 2:4] = 1
    regiao = {"id": 1, "evidencia": {"coco": []}}

    resultado = aplicar_politica(
        mascara,
        placa,
        [regiao],
        labels,
        np.zeros_like(placa),
        p_maior_que_limite=False,
        origem_base=True,
    )

    assert np.all(resultado[2:4, 2:4] == 1)


def test_candidatas_fora_das_bases_ficam_255_e_sam_aprovado_tem_prioridade():
    placa = np.ones((8, 8), dtype=bool)
    mascara = np.ones((8, 8), dtype=np.uint8)
    mascara[2, 2] = 2
    mascara[3, 3] = 255
    candidatas = np.zeros((8, 8), dtype=bool)
    candidatas[2:5, 2:5] = True

    resultado = aplicar_politica(
        mascara,
        placa,
        [],
        np.zeros((8, 8), dtype=np.int32),
        candidatas,
        p_maior_que_limite=True,
        origem_base=False,
    )

    assert resultado[2, 2] == 2
    assert resultado[3, 3] == 255
    assert resultado[4, 4] == 255
    assert resultado[0, 0] == 1
