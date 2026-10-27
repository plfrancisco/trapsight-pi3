"""A completude é cobrada por placa, área e decisão sem omitir insetos grandes."""

import numpy as np
import pytest

from training.estruturas_bases import (
    aplicar_decisoes,
    inventariar,
    medir_decisoes,
    restaurar_rle,
    validar_aceite_bases,
    validar_inventario,
)
from training.segmentar_regioes_revisadas import codificar_rle, segmentar


def test_inventario_preserva_inseto_grande_e_exclui_so_estrutura_desenhada():
    rgb = np.full((160, 180, 3), 230, np.uint8)
    rgb[10:110, 10:110] = 40
    rgb[:, 140:143] = 0
    estrutura = np.zeros((160, 180), bool)
    estrutura[:, 140:143] = True
    _, regioes = inventariar(rgb, np.ones((160, 180), bool), estrutura)
    assert len(regioes) == 1
    assert regioes[0]["area_candidata_px"] == 10000
    assert regioes[0]["decisao"] is None


def test_area_ambigua_respeita_tambem_o_limite_em_pp_da_placa():
    placa = np.ones((100, 100), bool)
    labels = np.zeros((100, 100), np.int32)
    labels.flat[:950] = 1
    labels.flat[950:1000] = 2
    regioes = [
        {"id": 1, "area_candidata_px": 950, "decisao": "inseto"},
        {"id": 2, "area_candidata_px": 50, "decisao": "ambigua"},
    ]
    resultado = medir_decisoes(labels, regioes, np.ones((100, 100), np.uint8), placa)
    assert resultado["fracao_area_ambigua"] == 0.05
    assert resultado["area_ambigua_pp_placa"] == 0.5
    assert not resultado["aceita"]
    regioes[1]["decisao"] = "sujeira"
    assert medir_decisoes(labels, regioes, np.ones((100, 100), np.uint8), placa)[
        "aceita"
    ]
    regioes[0]["decisao"] = None
    assert not medir_decisoes(labels, regioes, np.ones((100, 100), np.uint8), placa)[
        "aceita"
    ]


def test_sujeira_confirmada_nao_e_ignorada_e_inseto_recupera_buraco():
    placa = np.ones((10, 10), bool)
    labels = np.zeros((10, 10), np.int32)
    labels[1, 1] = 1
    labels[2, 2] = 2
    labels[3, 3] = 3
    regioes = [
        {"id": 1, "decisao": "sujeira"},
        {"id": 2, "decisao": "ambigua"},
        {"id": 3, "decisao": "inseto"},
    ]
    silhuetas = np.zeros_like(placa)
    silhuetas[1:4, 1:4] = True
    nova = aplicar_decisoes(placa, np.zeros_like(placa), labels, regioes, silhuetas)
    assert nova[1, 1] == 1
    assert nova[2, 2] == 255
    assert nova[3, 3] == 2
    assert nova[4, 4] == 1


def test_candidata_escura_nao_vira_silhueta_sem_anotacao_independente():
    placa = np.ones((10, 10), bool)
    labels = np.ones((10, 10), np.int32)
    nova = aplicar_decisoes(
        placa,
        np.zeros_like(placa),
        labels,
        [{"id": 1, "decisao": "inseto"}],
        np.zeros_like(placa),
    )
    assert not (nova == 2).any()


def test_inventario_recusa_caixa_alterada_e_regiao_omitida():
    referencia = [{"id": 1, "caixa": [1, 2, 3, 4], "area_candidata_px": 5}]
    validar_inventario(referencia, referencia)
    with pytest.raises(ValueError, match="Inventário mudou"):
        validar_inventario([], referencia)
    with pytest.raises(ValueError, match="Inventário mudou"):
        validar_inventario([{**referencia[0], "caixa": [0, 2, 3, 4]}], referencia)


def test_rle_preserva_silhueta_e_recusa_coordenadas_invalidas():
    silhueta = np.zeros((10, 12), bool)
    silhueta[2:5, 3:8] = True
    assert np.array_equal(restaurar_rle(codificar_rle(silhueta), (10, 12)), silhueta)
    for rle in ([[10, 0, 1]], [[0, -1, 2]], [[0, 1, 13]], [[0, 3, 3]]):
        with pytest.raises(ValueError, match="RLE"):
            restaurar_rle(rle, (10, 12))


def test_sam_so_segmenta_classe_previamente_decidida():
    class Predictor:
        def predict(self, **kwargs):
            mascara = np.ones((10, 10), bool)
            return np.array([mascara]), np.array([0.99]), None

    rgb = np.zeros((10, 10, 3), np.uint8)
    labels = np.ones((10, 10), np.int32)
    regiao = {"id": 1, "caixa": [0, 0, 10, 10], "decisao": "sujeira"}
    with pytest.raises(ValueError, match="semanticamente"):
        segmentar(Predictor(), rgb, labels, regiao)
    regiao["decisao"] = "inseto"
    proposta = segmentar(Predictor(), rgb, labels, regiao)
    assert proposta["revisao_silhueta"] == "pendente"
    assert "decisao" not in proposta


def test_guarda_aceita_so_bases_elegiveis_e_rejeita_area_255_acima_do_limite():
    with pytest.raises(ValueError, match="elegíveis"):
        validar_aceite_bases(
            {"revisao_visual": "aprovada", "placas": [{"depois": {"completude": 1}}]}
        )
    manifesto = {
        "versao": "bases_semanticas_v5",
        "revisao_visual": "parcialmente_aprovada",
        "limite_base_255_pp": 1.0,
        "bases_elegiveis": ["a"],
        "placas": [
            {
                "placa": "a",
                "base_elegivel": True,
                "revisao_visual": "aprovada",
                "medidas": {
                    "aceita": True,
                    "regioes": {"sem_decisao": 0},
                    "area_255_pp": 0.9,
                },
            },
            {
                "placa": "b",
                "base_elegivel": False,
                "revisao_visual": "aprovada",
                "medidas": {"aceita": False, "area_255_pp": 2.0},
            },
        ],
    }
    validar_aceite_bases(manifesto)
    manifesto["placas"][0]["revisao_visual"] = "pendente"
    with pytest.raises(ValueError, match="elegíveis"):
        validar_aceite_bases(manifesto)
    manifesto["placas"][0]["revisao_visual"] = "aprovada"
    manifesto["placas"][0]["medidas"]["area_255_pp"] = 1.001
    with pytest.raises(ValueError, match="elegíveis"):
        validar_aceite_bases(manifesto)
