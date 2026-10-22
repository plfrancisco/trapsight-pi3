"""Treino de ponta a ponta em CPU, com um dataset minúsculo."""

from __future__ import annotations

import csv
import json
import re

import pytest
from PIL import Image

from training.treino.dados import DatasetInvalido
from training.treino.loop import avaliar_teste, comparar_execucoes, treinar


def _silencioso(_mensagem: str) -> None:
    return None


def test_treino_grava_execucao_metricas_e_checkpoints(configuracao_rapida):
    pasta = treinar(configuracao_rapida, registro=_silencioso)

    execucao = json.loads((pasta / "execucao.json").read_text(encoding="utf-8"))
    linhas = list(
        csv.DictReader((pasta / "metricas_por_epoca.csv").open(encoding="utf-8"))
    )

    assert len(linhas) == 2 == execucao["epocas_executadas"]
    for arquivo in (
        "melhor.pt",
        "melhor_dice.pt",
        "ultimo.pt",
        "metricas_validacao.jsonl",
    ):
        assert (pasta / arquivo).exists()
    assert re.fullmatch(r"v0\.1\.0\+[0-9a-f]{8}", execucao["modelo_versao"])
    assert execucao["semente_global"] == configuracao_rapida.semente_global
    assert len(execucao["dataset"]["hash_metadados_sha256"]) == 64
    assert set(execucao["dataset"]["sementes_por_conjunto"]) == {"treino", "validacao"}
    assert execucao["configuracao"]["batch_efetivo_real"] == 4
    assert len(execucao["configuracao"]["pesos_de_classe"]) == 3
    assert {"torch", "albumentations", "torchmetrics"} <= set(execucao["bibliotecas"])
    assert execucao["hardware"]["dispositivo"] in {"cpu", "cuda"}
    assert execucao["melhor_ponto"]["epoca"] in {1, 2}


def test_treino_nunca_abre_imagens_do_conjunto_de_teste(
    configuracao_rapida, monkeypatch
):
    abertos: list[str] = []
    original = Image.open

    def espiao(caminho, *args, **kwargs):
        abertos.append(str(caminho))
        return original(caminho, *args, **kwargs)

    monkeypatch.setattr(Image, "open", espiao)

    treinar(configuracao_rapida, registro=_silencioso)

    assert abertos
    assert not [caminho for caminho in abertos if "teste_" in caminho]


def test_mesma_semente_repete_as_metricas_de_validacao(configuracao_rapida, tmp_path):
    primeira = treinar(configuracao_rapida.com(nome="a"), registro=_silencioso)
    segunda = treinar(configuracao_rapida.com(nome="b"), registro=_silencioso)

    comparacao = comparar_execucoes(primeira, segunda)

    assert comparacao["epocas_comparadas"] == 2
    assert comparacao["diferenca_maxima_erro_pp"] <= 0.2


def test_treino_recusa_dataset_com_semente_compartilhada(
    configuracao_rapida, criar_dataset
):
    criar_dataset(semente_compartilhada=True)  # regrava o mesmo dataset, agora inválido

    with pytest.raises(DatasetInvalido):
        treinar(configuracao_rapida, registro=_silencioso)


def test_teste_e_medido_uma_vez_por_checkpoint(configuracao_rapida):
    pasta = treinar(configuracao_rapida, registro=_silencioso)

    primeira = avaliar_teste(pasta, registro=_silencioso)
    resultado = json.loads(primeira.read_text(encoding="utf-8"))

    assert resultado["amostras_teste"] == 6
    assert resultado["metricas"]["amostras"] == 6
    assert len(resultado["checkpoint_sha256"]) == 64
    with pytest.raises(FileExistsError):
        avaliar_teste(pasta, registro=_silencioso)
    nova = avaliar_teste(pasta, registro=_silencioso, reavaliar=True)
    assert nova != primeira and nova.exists() and primeira.exists()


def test_teste_recusa_metadados_alterados_depois_do_treino(configuracao_rapida):
    pasta = treinar(configuracao_rapida, registro=_silencioso)
    metadados = pasta.parent.parent / "dataset" / "metadados.jsonl"
    metadados.write_text(metadados.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="mudaram"):
        avaliar_teste(pasta, registro=_silencioso)
