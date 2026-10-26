"""Leitura, verificação e pesos do dataset de treino."""

from __future__ import annotations

import json

import numpy as np
import pytest
from PIL import Image

from training.treino.dados import (
    DatasetInvalido,
    amostrar,
    contar_pixels_por_classe,
    correlacao_idade_cobertura,
    derivar_semente,
    exigir_dataset_valido,
    ler_dataset,
    percentual_da_mascara,
    pesos_de_classe,
    verificar_estrutura,
    verificar_mascaras,
)


def test_dataset_valido_passa_em_todas_as_verificacoes(criar_dataset):
    info = ler_dataset(criar_dataset())

    assert len(info.do_conjunto("treino")) == 6
    assert verificar_estrutura(info) == []
    exigir_dataset_valido(info)


def test_hash_dos_metadados_e_estavel(criar_dataset):
    raiz = criar_dataset()

    assert ler_dataset(raiz).hash_metadados == ler_dataset(raiz).hash_metadados


def test_semente_em_dois_conjuntos_impede_o_treino(criar_dataset):
    info = ler_dataset(criar_dataset(semente_compartilhada=True))

    assert any("semente" in problema for problema in verificar_estrutura(info))
    with pytest.raises(DatasetInvalido):
        exigir_dataset_valido(info)


@pytest.mark.parametrize(
    "campos",
    [
        ("placa_base_id", "placa_base_id"),
        ("placas_origem_recortes", "placas_origem_recortes"),
        ("placa_base_id", "placas_origem_recortes"),
    ],
)
def test_placa_compartilhada_entre_conjuntos_impede_treino(criar_dataset, campos):
    raiz = criar_dataset()
    caminho = raiz / "metadados.jsonl"
    linhas = [json.loads(linha) for linha in caminho.read_text().splitlines()]
    for conjunto, campo in zip(("treino", "validacao"), campos):
        registro = next(r for r in linhas if r["conjunto"] == conjunto)
        registro[campo] = (
            ["placa_compartilhada"]
            if campo == "placas_origem_recortes"
            else "placa_compartilhada"
        )
    caminho.write_text("\n".join(json.dumps(r) for r in linhas))
    with pytest.raises(DatasetInvalido, match="Placa de origem placa_compartilhada"):
        exigir_dataset_valido(ler_dataset(raiz))


def test_classe_ignorada_nao_entra_no_percentual_nem_nos_pesos(criar_dataset):
    raiz = criar_dataset()
    info = ler_dataset(raiz)
    amostra = info.do_conjunto("treino")[0]
    with Image.open(amostra.mascara) as imagem:
        mascara = np.array(imagem)
    mascara[0, 0] = 255
    Image.fromarray(mascara).save(amostra.mascara)
    assert verificar_mascaras([amostra]) == []
    assert contar_pixels_por_classe([amostra]).sum() == mascara.size - 1
    assert percentual_da_mascara(np.array([[1, 2, 255]], dtype=np.uint8)) == 50.0


def test_faixa_ausente_no_treino_impede_o_treino(criar_dataset):
    info = ler_dataset(criar_dataset(faixa_do_treino="ok"))

    problemas = verificar_estrutura(info)

    assert any("Faixa" in problema and "treino" in problema for problema in problemas)


def test_correlacao_entre_idade_e_cobertura_impede_o_treino(criar_dataset):
    info = ler_dataset(criar_dataset(idade=lambda cobertura: cobertura))

    assert abs(correlacao_idade_cobertura(info.do_conjunto("treino"))) > 0.9
    assert any("Correlação" in p for p in verificar_estrutura(info))


def test_percentual_divergente_dos_metadados_e_detectado(criar_dataset):
    raiz = criar_dataset()
    caminho = raiz / "metadados.jsonl"
    linhas = [json.loads(linha) for linha in caminho.read_text().splitlines()]
    linhas[0]["percentual_cobertura_real"] += 2.0
    caminho.write_text("\n".join(json.dumps(linha) for linha in linhas))
    info = ler_dataset(raiz)

    problemas = verificar_mascaras(info.do_conjunto("treino"))

    assert len(problemas) == 1
    assert "treino_000" in problemas[0]


def test_verificacao_do_treino_nunca_abre_imagens_de_teste(criar_dataset):
    raiz = criar_dataset()
    for arquivo in (raiz / "mascaras").glob("teste_*.png"):
        arquivo.unlink()
    for arquivo in (raiz / "imagens").glob("teste_*.png"):
        arquivo.unlink()

    exigir_dataset_valido(ler_dataset(raiz))


def test_percentual_da_mascara_usa_a_area_da_placa_como_denominador():
    mascara = np.zeros((10, 10), dtype=np.uint8)
    mascara[:5, :] = 1
    mascara[:2, :] = 2

    assert percentual_da_mascara(mascara) == pytest.approx(40.0)
    assert percentual_da_mascara(np.zeros((4, 4), dtype=np.uint8)) is None


def test_pesos_de_classe_dao_mais_peso_a_classe_rara():
    contagens = np.array([6000, 3000, 1000])

    pesos = pesos_de_classe(contagens, expoente=0.5, teto=10.0)

    assert pesos[2] > pesos[1] > pesos[0]
    assert pesos[0] == pytest.approx(1.0)  # a classe mais frequente é a referência
    assert pesos[2] == pytest.approx((6000 / 1000) ** 0.5)


def test_pesos_de_classe_respeitam_o_teto():
    pesos = pesos_de_classe(np.array([990_000, 9_000, 1_000]), expoente=1.0, teto=5.0)

    assert pesos.max() == pytest.approx(5.0)


def test_classe_sem_pixels_no_treino_e_recusada():
    with pytest.raises(DatasetInvalido):
        pesos_de_classe(np.array([100, 0, 50]), expoente=0.5, teto=10.0)


def test_contagem_de_pixels_cobre_as_tres_classes(criar_dataset):
    info = ler_dataset(criar_dataset())

    contagens = contar_pixels_por_classe(info.do_conjunto("treino"))

    assert contagens.sum() == 6 * 64 * 64
    assert (contagens > 0).all()


def test_amostragem_e_reprodutivel_e_respeita_o_limite(criar_dataset):
    amostras = ler_dataset(criar_dataset()).do_conjunto("treino")

    primeira = amostrar(amostras, 3, semente=5)

    assert primeira == amostrar(amostras, 3, semente=5)
    assert len(primeira) == 3
    assert amostrar(amostras, None, semente=5) == amostras


def test_semente_derivada_varia_por_epoca_e_indice_mas_e_reprodutivel():
    assert derivar_semente(1, 2, 3) == derivar_semente(1, 2, 3)
    assert derivar_semente(1, 2, 3) != derivar_semente(1, 3, 3)
    assert derivar_semente(1, 2, 3) != derivar_semente(1, 2, 4)
