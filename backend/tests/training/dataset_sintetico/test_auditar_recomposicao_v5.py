"""Valida a calibração reprodutível e os limites do auditor v5."""

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from training.auditar_recomposicao_v5 import (
    _normalizar_json,
    calcular_correlacao_idade_cobertura,
    comparar_reprodutibilidade,
    medir_calibracao_colagens,
    medir_espalhamento_dataset,
    medir_trocar_contra_aleatoria,
)
from training.dataset_sintetico import RecorteInsetoReal
from training.treino.dados import Amostra


def test_normalizar_json_converte_escalas_numpy_em_tipos_nativos() -> None:
    valor = _normalizar_json(
        {"medidas": [np.bool_(True), np.int64(3), np.float32(0.5)]}
    )

    assert json.loads(json.dumps(valor)) == {"medidas": [True, 3, 0.5]}


def test_correlacao_usa_todos_os_conjuntos():
    amostras = [
        Amostra(
            identificador=f"amostra_{indice}",
            semente=indice,
            conjunto=conjunto,
            faixa="ok",
            percentual_real=float(cobertura),
            idade_dias=float(indice),
            dominante_cor="neutra",
            imagem=Path(f"imagem_{indice}.png"),
            mascara=Path(f"mascara_{indice}.png"),
        )
        for indice, (conjunto, cobertura) in enumerate(
            (
                ("treino", 0),
                ("treino", 1),
                ("treino", 2),
                ("validacao", 2),
                ("teste", 1),
                ("teste", 0),
            )
        )
    ]

    assert calcular_correlacao_idade_cobertura(amostras) == pytest.approx(0.0)


def test_calibracao_de_colagens_e_reprodutivel_e_aplica_reuso_dois():
    recortes = []
    for indice in range(450):
        imagem = Image.new("RGBA", (7, 5), (0, 0, 0, 0))
        ImageDraw.Draw(imagem).ellipse((1, 1, 5, 3), fill=(25, 18, 12, 255))
        recortes.append(
            RecorteInsetoReal(
                identificador=f"placa__coco{indice}",
                placa_origem="placa",
                imagem=imagem,
                area_px=15,
                anotacao_coco_id=str(indice),
                taxon="Diptera",
            )
        )

    primeiro = medir_calibracao_colagens(
        recortes, area_placa_px=220_000, fator_escala=1.0, repeticoes=2
    )
    segundo = medir_calibracao_colagens(
        recortes, area_placa_px=220_000, fator_escala=1.0, repeticoes=2
    )

    assert primeiro == segundo
    assert primeiro["repeticoes"] == 2
    assert set(primeiro["resultados"]) == {"300", "900"}
    assert all(
        item["colagens"] in (300, 900) for item in primeiro["resultados"].values()
    )


def test_calibracao_recusa_biblioteca_menor_que_450_recortes():
    with pytest.raises(ValueError, match="450 recortes"):
        medir_calibracao_colagens([], area_placa_px=220_000, fator_escala=1.0)


def test_espalhamento_exige_amostra_minima_de_cem(tmp_path):
    (tmp_path / "imagens").mkdir()
    (tmp_path / "mascaras").mkdir()
    Image.new("RGB", (768, 576), (230, 230, 220)).save(
        tmp_path / "imagens" / "amostra_000001.png"
    )
    Image.new("L", (768, 576), 1).save(tmp_path / "mascaras" / "amostra_000001.png")

    resultado = medir_espalhamento_dataset(tmp_path)

    assert resultado["amostras_medidas"] == 1
    assert resultado["minimo_amostras"] == 100
    assert not resultado["amostras_suficientes"]
    assert not resultado["aceita"]


def test_comparacao_sha256_confirma_duas_execucoes_identicas(tmp_path):
    diretorios = [tmp_path / "a", tmp_path / "b"]
    for diretorio in diretorios:
        (diretorio / "imagens").mkdir(parents=True)
        (diretorio / "mascaras").mkdir()
        Image.new("RGB", (8, 8), (10, 20, 30)).save(
            diretorio / "imagens" / "amostra_000001.png"
        )
        Image.new("L", (8, 8), 2).save(diretorio / "mascaras" / "amostra_000001.png")
        (diretorio / "metadados.jsonl").write_text(
            '{"id":"amostra_000001","semente":1}\n', encoding="utf-8"
        )

    resultado = comparar_reprodutibilidade(*diretorios, quantidade=1)

    assert resultado["amostras_comparadas"] == 1
    assert resultado["arquivos_comparados"] == 3
    assert resultado["arquivos_identicos"] == 3
    assert resultado["aceita"]


def test_trocar_compara_mascaras_com_colagem_uniforme(tmp_path):
    dataset = tmp_path / "dataset"
    (dataset / "imagens").mkdir(parents=True)
    (dataset / "mascaras").mkdir()
    imagem = Image.new("RGB", (768, 576), (230, 230, 220))
    mascara = Image.new("L", (768, 576), 0)
    ImageDraw.Draw(mascara).rectangle((100, 100, 667, 375), fill=1)
    ImageDraw.Draw(mascara).rectangle((201, 150, 500, 280), fill=2)
    imagem.save(dataset / "imagens" / "amostra_000001.png")
    mascara.save(dataset / "mascaras" / "amostra_000001.png")
    (dataset / "configuracao.json").write_text(
        '{"resolucao":[768,576],"fator_escala_recorte":1.0}', encoding="utf-8"
    )
    (dataset / "metadados.jsonl").write_text(
        '{"id":"amostra_000001","faixa_cobertura_alvo":"trocar",'
        '"recortes_coco_ids_usados":["placa__coco1"],"origem_base":'
        '"sintetica_stickfly_k45","semente":11,"percentual_cobertura_real":25.0}\n',
        encoding="utf-8",
    )
    recorte = Image.new("RGBA", (12, 12), (0, 0, 0, 0))
    ImageDraw.Draw(recorte).ellipse((1, 1, 10, 10), fill=(20, 15, 10, 255))
    registro_recorte = RecorteInsetoReal(
        identificador="placa__coco1",
        placa_origem="placa",
        imagem=recorte,
        area_px=80,
    )

    resultado = medir_trocar_contra_aleatoria(
        dataset, [registro_recorte], tmp_path, tmp_path
    )

    assert resultado["amostras"] == 1
    assert "diferenca_aglomeracao_media" in resultado
    assert "ocupacao_uniforme_media" in resultado
