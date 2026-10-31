"""Treino de ponta a ponta em CPU, com um dataset minúsculo."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import torch
from PIL import Image

from training.treino import loop
from training.treino.dados import DatasetInvalido
from training.treino.loop import avaliar_teste, comparar_execucoes, treinar


def _silencioso(_mensagem: str) -> None:
    return None


@pytest.mark.parametrize("estouro", [False, True], ids=["acima_da_folga", "oom"])
def test_sonda_recusa_todos_os_lotes_sem_gpu(configuracao_rapida, monkeypatch, estouro):
    modelo = MagicMock()
    modelo.to.return_value = modelo
    modelo.parameters.return_value = [torch.nn.Parameter(torch.zeros(1))]
    modelo.return_value = torch.ones(1, requires_grad=True)
    monkeypatch.setattr(loop, "criar_modelo", lambda _config: modelo)
    monkeypatch.setattr(loop, "colocar_em_treino", lambda *_args: None)
    monkeypatch.setattr(torch.cuda, "empty_cache", lambda: None)
    monkeypatch.setattr(torch.cuda, "mem_get_info", lambda _device: (100, 100))
    monkeypatch.setattr(torch.cuda, "reset_peak_memory_stats", lambda _device: None)
    monkeypatch.setattr(torch.cuda, "max_memory_reserved", lambda _device: 76)
    tentativas = []

    def entrada_cpu(candidato, *_args, **_kwargs):
        tentativas.append(candidato)
        if estouro:
            raise torch.cuda.OutOfMemoryError("VRAM simulada insuficiente")
        return torch.zeros(candidato, 3, 2, 2)

    monkeypatch.setattr(torch, "randn", entrada_cpu)
    monkeypatch.setattr(torch, "randint", lambda *_args, **_kwargs: torch.zeros(1))

    def perda(logits, _alvo):
        return SimpleNamespace(total=logits.sum())

    with pytest.raises(RuntimeError, match="nem o lote 1") as erro:
        loop.descobrir_lote_por_passo(
            configuracao_rapida.com(batch_por_passo="auto"),
            perda,
            torch.device("cuda"),
        )

    assert tentativas == [4, 2, 1]
    assert "somente no teste de fumaça E0" in str(erro.value)
    assert "gradient checkpointing no encoder" in str(erro.value)
    assert "outra GPU" in str(erro.value)


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


@pytest.fixture
def modelo_minimo(monkeypatch):
    """Substitui a U-Net para testar falhas numéricas rapidamente em CPU."""

    class ModeloMinimo(torch.nn.Module):
        """Mantém os grupos de parâmetros esperados pelo otimizador."""

        def __init__(self):
            super().__init__()
            self.encoder = torch.nn.Conv2d(3, 3, 1)
            self.decoder = torch.nn.Identity()
            self.segmentation_head = torch.nn.Conv2d(3, 3, 1)

        def forward(self, imagens):
            """Produz logits pequenos com gradiente para as três classes."""
            return self.segmentation_head(self.decoder(self.encoder(imagens)))

    modelo = ModeloMinimo()
    monkeypatch.setattr(loop, "criar_modelo", lambda _config: modelo)
    return modelo


@pytest.mark.parametrize("etapa", ["treino", "validação"])
@pytest.mark.parametrize("valor", [float("nan"), float("inf"), -float("inf")])
def test_perda_nao_finita_aborta_sem_checkpoint_nem_selecao(
    configuracao_rapida, monkeypatch, modelo_minimo, etapa, valor
):
    original = loop.PerdaSegmentacao.forward
    chamadas = {"treino": 0, "validação": 0}

    def perda_invalida(self, logits, mascaras):
        fase = "treino" if torch.is_grad_enabled() else "validação"
        chamadas[fase] += 1
        resultado = original(self, logits, mascaras)
        if fase == etapa:
            return SimpleNamespace(total=resultado.total * valor)
        return resultado

    monkeypatch.setattr(loop.PerdaSegmentacao, "forward", perda_invalida)
    selecao = MagicMock(side_effect=AssertionError("Época inválida chegou à seleção"))
    monkeypatch.setattr(loop.SelecaoMelhorPonto, "atualizar", selecao)
    with pytest.raises(FloatingPointError, match=f"Perda não finita em {etapa}"):
        treinar(
            configuracao_rapida, registro=_silencioso, dispositivo=torch.device("cpu")
        )

    pasta = next(Path(configuracao_rapida.saida).iterdir())
    execucao = json.loads((pasta / "execucao.json").read_text("utf-8"))
    assert execucao["status"] == "abortada"
    assert execucao["erro"]["tipo"] == "FloatingPointError"
    assert execucao["erro"]["epoca"] == 1
    assert etapa in execucao["erro"]["mensagem"]
    assert str(valor) in execucao["erro"]["mensagem"]
    assert execucao["epocas_executadas"] == 0
    assert execucao["melhor_ponto"] == {}
    assert execucao["modelo_versao"] is None
    assert execucao["finalizada_em"]
    assert not list(pasta.glob("*.pt"))
    assert not (pasta / "metricas_validacao.jsonl").exists()
    with (pasta / "metricas_por_epoca.csv").open(encoding="utf-8") as arquivo:
        assert list(csv.DictReader(arquivo)) == []
    assert chamadas[etapa] == 1
    selecao.assert_not_called()


@pytest.mark.parametrize("etapa", ["treino", "validação"])
def test_nan_preserva_checkpoints_e_melhor_ponto_da_epoca_valida(
    configuracao_rapida, monkeypatch, modelo_minimo, etapa
):
    original_perda = loop.PerdaSegmentacao.forward
    original_checkpoint = loop.gravar_checkpoint
    original_selecao = loop.SelecaoMelhorPonto.atualizar
    chamadas = {"treino": 0, "validação": 0}
    checkpoints = {}
    selecoes = []

    def perda_nan(self, logits, mascaras):
        fase = "treino" if torch.is_grad_enabled() else "validação"
        chamadas[fase] += 1
        resultado = original_perda(self, logits, mascaras)
        if fase == etapa and chamadas[fase] == 4:
            return SimpleNamespace(total=resultado.total * float("nan"))
        return resultado

    def gravar(modelo, configuracao, caminho):
        versao = original_checkpoint(modelo, configuracao, caminho)
        assert caminho.name not in checkpoints
        checkpoints[caminho.name] = caminho.read_bytes()
        return versao

    def selecionar(self, metricas):
        selecoes.append(metricas)
        return original_selecao(self, metricas)

    monkeypatch.setattr(loop.PerdaSegmentacao, "forward", perda_nan)
    monkeypatch.setattr(loop, "gravar_checkpoint", gravar)
    monkeypatch.setattr(loop.SelecaoMelhorPonto, "atualizar", selecionar)
    with pytest.raises(FloatingPointError, match="época 2"):
        treinar(
            configuracao_rapida, registro=_silencioso, dispositivo=torch.device("cpu")
        )

    pasta = next(Path(configuracao_rapida.saida).iterdir())
    execucao = json.loads((pasta / "execucao.json").read_text("utf-8"))
    assert execucao["erro"]["epoca"] == 2
    assert execucao["epocas_executadas"] == 1
    assert execucao["melhor_ponto"]["epoca"] == 1
    assert execucao["modelo_versao"] == execucao["melhor_ponto"]["modelo_versao"]
    assert len(selecoes) == 1
    assert set(checkpoints) == {"melhor.pt", "melhor_dice.pt", "ultimo.pt"}
    for nome, conteudo in checkpoints.items():
        assert (pasta / nome).read_bytes() == conteudo
    with (pasta / "metricas_por_epoca.csv").open(encoding="utf-8") as arquivo:
        assert [linha["epoca"] for linha in csv.DictReader(arquivo)] == ["1"]
    assert (
        len((pasta / "metricas_validacao.jsonl").read_text("utf-8").splitlines()) == 1
    )


def test_perda_media_de_validacao_nan_nao_chega_a_selecao(
    configuracao_rapida, monkeypatch, modelo_minimo
):
    monkeypatch.setattr(loop, "validar", lambda *_: ({}, float("nan")))
    with pytest.raises(FloatingPointError, match="validação, época 1"):
        treinar(
            configuracao_rapida, registro=_silencioso, dispositivo=torch.device("cpu")
        )
    pasta = next(Path(configuracao_rapida.saida).iterdir())
    assert not list(pasta.glob("*.pt"))
    assert (
        json.loads((pasta / "execucao.json").read_text("utf-8"))["status"] == "abortada"
    )
