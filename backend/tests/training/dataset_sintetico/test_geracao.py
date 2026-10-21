"""Verifica as propriedades dos dados e arquivos gerados."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from training.dataset_sintetico import (
    calcular_correlacao_pearson,
    calcular_percentual_cobertura,
)


def test_idade_e_cobertura_tem_correlacao_proxima_de_zero(
    tmp_path: Path,
    gerar_dataset_teste,
) -> None:
    """Garante independência prática entre idade simulada e cobertura real."""
    registros = gerar_dataset_teste(tmp_path / "dataset", quantidade=180)
    idades = [float(registro["idade_simulada_dias"]) for registro in registros]
    coberturas = [
        float(registro["percentual_cobertura_real"]) for registro in registros
    ]

    assert abs(calcular_correlacao_pearson(idades, coberturas)) < 0.15
    contagens_faixas = (
        sum(cobertura < 40 for cobertura in coberturas),
        sum(40 <= cobertura < 70 for cobertura in coberturas),
        sum(cobertura >= 70 for cobertura in coberturas),
    )
    assert all(50 <= quantidade_faixa <= 70 for quantidade_faixa in contagens_faixas)


def test_percentual_registrado_e_calculado_a_partir_da_mascara(
    tmp_path: Path,
    gerar_dataset_teste,
) -> None:
    """Confere o percentual de cada amostra diretamente na máscara PNG."""
    saida = tmp_path / "dataset"
    registros = gerar_dataset_teste(saida, quantidade=6, semente=18)

    for registro in registros:
        caminho_mascara = saida / "mascaras" / f"{registro['id']}.png"
        with Image.open(caminho_mascara) as imagem_mascara:
            mascara = imagem_mascara.convert("L")
        classes = set(mascara.tobytes())
        assert classes <= {0, 1, 2}
        assert (
            calcular_percentual_cobertura(mascara)
            == registro["percentual_cobertura_real"]
        )


def test_mesma_semente_produz_arquivos_identicos(
    tmp_path: Path,
    gerar_dataset_teste,
) -> None:
    """Compara byte a byte duas gerações com a mesma configuração."""
    primeira = tmp_path / "primeira"
    segunda = tmp_path / "segunda"
    gerar_dataset_teste(primeira, quantidade=9, semente=77)
    gerar_dataset_teste(segunda, quantidade=9, semente=77)

    arquivos_primeiros = {
        caminho.relative_to(primeira): caminho.read_bytes()
        for caminho in primeira.rglob("*")
        if caminho.is_file()
    }
    arquivos_segundos = {
        caminho.relative_to(segunda): caminho.read_bytes()
        for caminho in segunda.rglob("*")
        if caminho.is_file()
    }
    assert arquivos_primeiros == arquivos_segundos


def test_geracao_rejeita_diretorio_de_saida_nao_vazio(
    tmp_path: Path,
    gerar_dataset_teste,
) -> None:
    """Preserva os arquivos quando o diretório de saída já contém dados."""
    saida = tmp_path / "dataset"
    saida.mkdir()
    marcador = saida / "dados-existentes.txt"
    marcador.write_text("preservar", encoding="utf-8")

    with pytest.raises(FileExistsError, match="não está vazio"):
        gerar_dataset_teste(saida, quantidade=1)

    assert marcador.read_text(encoding="utf-8") == "preservar"
