import json

import numpy as np

from training.revisar_originais_ums import Transformacao
from training.segmentar_coco_originais import (
    _projetar_mascara,
    agrupar_caixas,
    conservar_recortes_de_composicao,
    medir_qc,
    selecionar_proposta,
)


def test_agrupar_caixas_preserva_margem_e_ids_unicos():
    anotacoes = [
        {"id": 3, "bbox": [300.0, 400.0, 32.0, 24.0]},
        {"id": 1, "bbox": [350.0, 420.0, 30.0, 28.0]},
        {"id": 2, "bbox": [800.0, 900.0, 20.0, 18.0]},
    ]

    janelas = agrupar_caixas(anotacoes, 10200, 14039)

    assert {a["id"] for j in janelas for a in j.anotacoes} == {1, 2, 3}
    assert sum(len(j.anotacoes) for j in janelas) == 3
    assert all(
        256 <= max(j.xyxy[2] - j.xyxy[0], j.xyxy[3] - j.xyxy[1]) <= 1024
        for j in janelas
    )
    for janela in janelas:
        x0, y0, x1, y1 = janela.xyxy
        for anotacao in janela.anotacoes:
            x, y, w, h = anotacao["bbox"]
            assert x0 <= x - 64
            assert y0 <= y - 64
            assert x1 >= x + w + 64
            assert y1 >= y + h + 64


def test_qc_aceita_area_correta_e_componente_principal():
    mascara = np.zeros((64, 64), dtype=bool)
    mascara[18:44, 18:44] = True
    mascara[2, 2] = True

    medicao = medir_qc(mascara, (16, 16, 48, 48), 0.91)

    assert medicao["aprovada"]
    assert medicao["area_componente_px"] == 26 * 26
    assert medicao["cobertura_bbox_coco"] >= 0.60


def test_qc_reprova_area_muito_pequena():
    mascara = np.zeros((64, 64), dtype=bool)
    mascara[30:34, 30:34] = True

    medicao = medir_qc(mascara, (16, 16, 48, 48), 0.99)

    assert not medicao["aprovada"]
    assert "area_menor_que_25_porcento_da_caixa" in medicao["motivos"]


def test_selecionar_proposta_prefere_candidata_aprovada():
    mascaras = np.zeros((2, 64, 64), dtype=bool)
    mascaras[0, 30:34, 30:34] = True
    mascaras[1, 18:44, 18:44] = True

    escolhida = selecionar_proposta(mascaras, np.array([0.99, 0.91]), (16, 16, 48, 48))

    assert escolhida["aprovada"]
    assert escolhida["score_sam"] == 0.91
    assert len(escolhida["candidatas_qc"]) == 2


def test_projecao_reduz_por_area_e_preserva_contagem_esperada():
    transformacao = Transformacao(10200, 14039, 768, 558, 0, 9)
    mascara = np.zeros((500, 500), dtype=bool)
    mascara[200:300, 200:300] = True

    projetada, esperada, quantidade = _projetar_mascara(
        mascara, (1000, 2000, 1500, 2500), transformacao
    )

    assert projetada.shape == (576, 768)
    assert quantidade == int(projetada.sum())
    assert abs(quantidade - esperada) / esperada <= 0.10


def test_biblioteca_final_remove_recortes_de_placas_de_avaliacao(tmp_path):
    biblioteca = tmp_path / "recortes"
    (biblioteca / "catalogos").mkdir(parents=True)
    for nome in ("composicao_a", "avaliacao_b"):
        (biblioteca / nome).mkdir()
        (biblioteca / nome / "00000001.png").write_bytes(b"recorte")
        (biblioteca / "catalogos" / f"{nome}.jsonl").write_text("{}\n")
    (biblioteca / "configuracao.json").write_text(
        json.dumps({"recortes_por_placa": {"composicao_a": 1, "avaliacao_b": 1}}),
        encoding="utf-8",
    )

    resumo = conservar_recortes_de_composicao(
        biblioteca, {"composicao_a"}, {"avaliacao_b"}
    )

    assert resumo["catalogos_avaliacao_removidos"] == 1
    assert resumo["recortes_avaliacao_removidos"] == 1
    assert (biblioteca / "composicao_a").is_dir()
    assert not (biblioteca / "avaliacao_b").exists()
    assert not (biblioteca / "catalogos" / "avaliacao_b.jsonl").exists()
    configuracao = json.loads((biblioteca / "configuracao.json").read_text())
    assert configuracao["placas_avaliacao_excluidas"] == ["avaliacao_b"]
