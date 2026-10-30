"""Avaliação pareada em CPU com gabaritos pequenos e modelo trivial."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree

import numpy as np
import pytest
import torch
from PIL import Image

from training.treino import avaliacao
from training.treino.avaliacao import (
    comparar_modelo_baseline,
    conferir_aprovacao,
    grafico_idade_svg,
)
from training.treino.dados import Amostra, InfoDataset, hash_arquivo, ler_dataset


class ModeloTrivial(torch.nn.Module):
    """Prediz placa limpa para evidenciar o erro crítico sem pesos treinados."""

    def forward(self, entrada):
        """Retorna logits de placa limpa com o tamanho da imagem recebida."""
        logits = torch.zeros((entrada.shape[0], 3, *entrada.shape[2:]))
        logits[:, 1] = 1
        return logits


@pytest.fixture
def info_minima(tmp_path):
    amostras = []
    for i in range(4):
        mascara = np.ones((4, 4), dtype=np.uint8)
        mascara[0] = 2
        # Metade das imagens contém uma região ambígua que não pode afetar métricas.
        if i % 2:
            mascara[:, 2:] = 255
        imagem = np.full((4, 4, 3), 250, dtype=np.uint8)
        imagem[mascara == 2] = 20
        imagem[mascara == 255] = 0
        img, mask = tmp_path / f"i{i}.png", tmp_path / f"m{i}.png"
        Image.fromarray(imagem).save(img)
        Image.fromarray(mascara).save(mask)
        amostras.append(
            Amostra(
                str(i),
                i,
                "teste",
                "trocar",
                25,
                i * 20,
                "creme",
                img,
                mask,
                origem_base="real_ums" if i % 2 else "sintetica_stickfly_k45",
                subconjuntos_avaliacao=("sujeira", "amarelamento", "iluminacao_angulo"),
            )
        )
    return InfoDataset(tmp_path, tuple(amostras), 7, "hash")


def test_comparacao_pareada_ignora_255_e_separa_bases(info_minima):
    modelo = ModeloTrivial().train()
    resultado = comparar_modelo_baseline(modelo, info_minima, 217)
    assert modelo.training
    assert resultado["modelo"]["trocar_como_ok"] == 4
    assert resultado["modelo"]["erro_percentual_medio_pp"] == 25
    assert resultado["baseline"]["erro_percentual_medio_pp"] == 0
    assert resultado["baseline"]["dice_coberta"] == 1
    assert resultado["baseline"]["iou_por_classe"]["placa_coberta"] == 1
    assert not resultado["aprovacao"]["atingiu_minimo"]
    assert resultado["subconjuntos_ausentes"] == []
    assert set(resultado["por_base"]) == {"real_ums", "sintetica_stickfly_k45"}
    for par in resultado["por_subconjunto"].values():
        assert par["modelo"]["amostras"] == par["baseline"]["amostras"] == 4
    for metodo in ("modelo", "baseline"):
        por_imagem = resultado[metodo]["por_imagem"]
        assert [m["id"] for m in por_imagem] == ["0", "1", "2", "3"]
        assert len(por_imagem[0]["imagem_sha256"]) == 64
    assert [p["idade_dias"] for p in resultado["curvas_erro_por_idade"]] == [
        5,
        25,
        45,
        65,
    ]
    svg = grafico_idade_svg(resultado["curvas_erro_por_idade"])
    raiz = ElementTree.fromstring(svg)
    assert len(raiz.findall("{http://www.w3.org/2000/svg}polyline")) == 2
    assert json.loads(json.dumps(resultado, allow_nan=False)) == resultado


@pytest.mark.parametrize(
    "dominio,erro,dice,acuracia",
    [
        ("sintetico", 1, 0.90, 0),
        ("real", 2, 0.80, 0.90),
    ],
)
def test_limites_inclusivos_e_erro_critico_soberano(dominio, erro, dice, acuracia):
    metricas = {
        "erro_percentual_medio_pp": erro,
        "dice_coberta": dice,
        "acuracia_status": acuracia,
        "trocar_como_ok": 0,
    }
    assert conferir_aprovacao(metricas, dominio)["atingiu_alvo"]
    metricas["trocar_como_ok"] = 1
    assert not conferir_aprovacao(metricas, dominio)["atingiu_minimo"]


@pytest.mark.parametrize(
    "dominio,erro,dice,acuracia",
    [
        ("sintetico", 2, 0.85, 0),
        ("real", 3, 0.75, 0.85),
    ],
)
def test_minimos_e_reprovacao_de_cada_metrica(dominio, erro, dice, acuracia):
    metricas = {
        "erro_percentual_medio_pp": erro,
        "dice_coberta": dice,
        "acuracia_status": acuracia,
        "trocar_como_ok": 0,
    }
    assert conferir_aprovacao(metricas, dominio)["atingiu_minimo"]
    assert not conferir_aprovacao(metricas, dominio)["atingiu_alvo"]
    for nome, variacao in (("erro_percentual_medio_pp", 0.01), ("dice_coberta", -0.01)):
        assert not conferir_aprovacao(
            {**metricas, nome: metricas[nome] + variacao}, dominio
        )["atingiu_minimo"]
    if dominio == "real":
        metricas["acuracia_status"] -= 0.01
        assert not conferir_aprovacao(metricas, dominio)["atingiu_minimo"]


def test_subconjuntos_ausentes_nao_sao_inventados(info_minima):
    info = replace(
        info_minima,
        amostras=tuple(
            replace(a, subconjuntos_avaliacao=()) for a in info_minima.amostras
        ),
    )
    resultado = comparar_modelo_baseline(ModeloTrivial(), info, 217)
    assert len(resultado["subconjuntos_ausentes"]) == 3
    assert all(v is None for v in resultado["por_subconjunto"].values())


def test_base_real_recomposta_nao_aprova_dominio_real(info_minima):
    class ModeloPorBrilho(torch.nn.Module):
        """Separa as duas cores artificiais sem carregar checkpoint."""

        def forward(self, entrada):
            """Retorna classes exatas da fixture, inclusive na região ignorada."""
            rotulos = torch.where(entrada.mean(dim=1) < 0, 2, 1)
            return torch.nn.functional.one_hot(rotulos, 3).permute(0, 3, 1, 2).float()

    resultado = comparar_modelo_baseline(ModeloPorBrilho(), info_minima, 217)
    assert resultado["aprovacao"]["dominio"] == "sintetico"
    assert resultado["aprovacao"]["atingiu_alvo"]
    assert resultado["aprovacao_geral"] == "pendente_outro_dominio"


def test_idade_invalida_e_teste_vazio_sao_recusados(info_minima):
    with pytest.raises(ValueError, match="vazio"):
        comparar_modelo_baseline(
            ModeloTrivial(), replace(info_minima, amostras=()), 217
        )
    info = replace(
        info_minima,
        amostras=(replace(info_minima.amostras[0], idade_dias=float("nan")),),
    )
    with pytest.raises(ValueError, match="Idades"):
        comparar_modelo_baseline(ModeloTrivial(), info, 217)


def test_curvas_agrupam_faixas_bordas_e_idades_iguais(info_minima):
    idades = (0.1, 9.9, 10.0, 10.0, 29.0, 89.9, 90.0, 99.0, 180.0)
    info = replace(
        info_minima,
        amostras=tuple(
            replace(
                info_minima.amostras[i % 4], identificador=f"{i:02d}", idade_dias=idade
            )
            for i, idade in enumerate(idades)
        ),
    )
    curvas = comparar_modelo_baseline(ModeloTrivial(), info, 217)[
        "curvas_erro_por_idade"
    ]
    assert [p["faixa"] for p in curvas] == ["0-10", "10-20", "20-30", "80-90", "90+"]
    assert [p["amostras"] for p in curvas] == [2, 2, 1, 1, 3]
    assert [p["idade_dias"] for p in curvas] == [5, 15, 25, 85, 95]
    assert [p["idade_inicio"] for p in curvas] == [0, 10, 20, 80, 90]
    assert [p["idade_fim"] for p in curvas] == [10, 20, 30, 90, None]
    assert all(p["modelo"] == 25 and p["baseline"] == 0 for p in curvas)
    assert sum(p["amostras"] for p in curvas) == len(idades)
    raiz = ElementTree.fromstring(grafico_idade_svg(curvas))
    textos = [t.text for t in raiz.findall("{http://www.w3.org/2000/svg}text")]
    assert all(p["faixa"] in textos for p in curvas)
    assert "30-40" not in textos
    json.dumps(curvas, allow_nan=False)


def test_imagem_inteiramente_ignorada_e_recusada_sem_deslocar_ids(info_minima):
    amostra = info_minima.amostras[1]
    Image.fromarray(np.full((4, 4), 255, dtype=np.uint8)).save(amostra.mascara)
    modelo = ModeloTrivial().train()
    with pytest.raises(ValueError, match=r"Amostra 1 sem pixels válidos.*255"):
        comparar_modelo_baseline(modelo, info_minima, 217)
    assert modelo.training


@pytest.mark.parametrize("dominio", ["sintetico", "real"])
def test_entrada_de_avaliacao_registra_versoes_e_preserva_historico(
    criar_dataset, tmp_path, monkeypatch, dominio
):
    from training.treino import modelo as modulo_modelo

    dataset = criar_dataset()
    pasta = tmp_path / "execucao"
    pasta.mkdir()
    (pasta / "melhor.pt").write_bytes(b"substituido por modelo trivial no teste")
    registro = {
        "identificador": "teste",
        "semente_global": 7,
        "dataset": {
            "caminho": str(dataset),
            "hash_metadados_sha256": hash_arquivo(dataset / "metadados.jsonl"),
        },
    }
    (pasta / "execucao.json").write_text(json.dumps(registro), encoding="utf-8")
    calibracao = tmp_path / "calibracao.json"
    calibracao.write_text('{"limiar_v": 217}', encoding="utf-8")
    monkeypatch.setattr(
        modulo_modelo, "carregar_checkpoint", lambda *_: (ModeloTrivial(), {})
    )
    primeiro = avaliacao.avaliar_teste(pasta, calibracao=calibracao, dominio=dominio)
    resultado = json.loads(primeiro.read_text("utf-8"))
    assert resultado["versao_relatorio"] == 2
    assert resultado["dominio"] == dominio
    assert resultado["comparacao"]["aprovacao"]["dominio"] == dominio
    assert ("acuracia_status" in resultado["comparacao"]["aprovacao"]["criterios"]) == (
        dominio == "real"
    )
    assert resultado["semente_global"] == 7
    assert resultado["bibliotecas"]["torch"]
    assert resultado["comparacao"]["aprovacao_geral"] == "reprovado"
    assert primeiro.with_suffix(".svg").exists()
    with pytest.raises(FileExistsError):
        avaliacao.avaliar_teste(pasta, calibracao=calibracao, dominio=dominio)
    novo = avaliacao.avaliar_teste(
        pasta, reavaliar=True, calibracao=calibracao, dominio=dominio
    )
    assert novo != primeiro and primeiro.exists()
    (dataset / "metadados.jsonl").write_text("\n", encoding="utf-8")
    with pytest.raises(ValueError):
        avaliacao.avaliar_teste(
            pasta, reavaliar=True, calibracao=calibracao, dominio=dominio
        )


def test_leitura_preserva_metadados_de_avaliacao(criar_dataset):
    raiz = criar_dataset()
    caminho = raiz / "metadados.jsonl"
    linhas = [json.loads(linha) for linha in caminho.read_text("utf-8").splitlines()]
    linhas[0].update(origem_base="real_ums", subconjuntos_avaliacao=["sujeira"])
    caminho.write_text(
        "\n".join(json.dumps(linha) for linha in linhas), encoding="utf-8"
    )
    amostra = ler_dataset(raiz).amostras[0]
    assert amostra.origem_base == "real_ums"
    assert amostra.subconjuntos_avaliacao == ("sujeira",)


def test_cli_existente_delega_avaliacao_e_comparacao(monkeypatch, capsys):
    from training.treino import __main__ as cli
    from training.treino import loop

    chamadas = []
    monkeypatch.setattr(
        avaliacao,
        "avaliar_teste",
        lambda pasta, **opcoes: (
            chamadas.append((pasta, opcoes)) or Path("resultado.json")
        ),
    )
    assert cli.main(["avaliar-teste", "--execucao", "pasta", "--reavaliar"]) == 0
    assert chamadas == [(Path("pasta"), {"reavaliar": True, "dominio": "sintetico"})]
    assert cli.main(["avaliar-teste", "--execucao", "pasta", "--dominio", "real"]) == 0
    assert chamadas[-1] == (Path("pasta"), {"reavaliar": False, "dominio": "real"})
    with pytest.raises(SystemExit):
        cli.main(["avaliar-teste", "--execucao", "pasta", "--dominio", "invalido"])
    monkeypatch.setattr(loop, "comparar_execucoes", lambda *_: {"epocas_comparadas": 2})
    assert cli.main(["comparar", "--a", "a", "--b", "b"]) == 0
    assert "epocas_comparadas" in capsys.readouterr().out
