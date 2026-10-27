"""Transformações e evidência COCO não podem produzir classes por aparência."""

import numpy as np
import pytest

from training.estruturas_bases import inventariar
from training.revisar_originais_ums import Transformacao, evidencias
from training.segmentar_originais_revisados import projetar


def test_transformacao_preserva_rotacao_e_letterbox_no_caminho_inverso():
    t = Transformacao(100, 200, 80, 40, 7, 11)
    assert t.direto(25, 50) == (27, 41)
    assert t.inverso(27, 41) == (25, 50)
    assert t.caixa([25, 50, 20, 30]) == [27, 33, 39, 41]
    for x, y in ((0, 0), (100, 200), (0.5, 25.5), (56.7, 89.1)):
        assert t.inverso(*t.direto(x, y)) == pytest.approx((x, y))


def test_ausencia_de_coco_nao_propoe_sujeira_e_presenca_nao_decide_classe():
    t = Transformacao(100, 200, 200, 100, 0, 0)
    anotacoes = [{"id": 4, "bbox": [20, 30, 10, 20], "taxon": "Diptera"}]
    assert evidencias([1, 1, 4, 4], anotacoes, t) == []
    proposta = evidencias([35, 75, 2, 2], anotacoes, t)[0]
    assert proposta["anotacao_id"] == 4
    assert proposta["taxon"] == "Diptera"
    assert "decisao" not in proposta


def test_projecao_de_centros_equivale_a_rotacao_sem_escala():
    original = np.zeros((20, 10), bool)
    original[3:5, 4:7] = True
    t = Transformacao(10, 20, 20, 10, 0, 0)
    resultado = projetar(original, [0, 0, 10, 20], t)
    assert np.array_equal(resultado[:10, :20], np.rot90(original))
    assert resultado.sum() == original.sum()


def test_refinar_estrutura_preserva_identificadores_das_outras_regioes():
    rgb = np.full((100, 100, 3), 230, np.uint8)
    rgb[10:12, 10:12] = 20
    rgb[50:53, 50:53] = 20
    placa = np.ones((100, 100), bool)
    estrutura = np.zeros_like(placa)
    _, anteriores = inventariar(rgb, placa, estrutura)
    estrutura[10:12, 10:12] = True
    labels, novas = inventariar(rgb, placa, estrutura, anteriores[1:])
    assert novas[0]["id"] == 2
    assert labels[51, 51] == 2
    assert not labels[10:12, 10:12].any()
