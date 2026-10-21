"""Verifica a independência entre idade simulada e cobertura."""

from __future__ import annotations

from pathlib import Path

from training.dataset_sintetico import calcular_correlacao_pearson


def test_idade_e_cobertura_tem_correlacao_proxima_de_zero(
    tmp_path: Path,
    gerar_dataset_teste,
) -> None:
    """Garante independência prática entre idade sorteada e cobertura real."""
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
