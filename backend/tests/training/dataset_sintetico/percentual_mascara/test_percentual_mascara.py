"""Verifica o percentual calculado a partir das máscaras persistidas."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from training.dataset_sintetico import calcular_percentual_cobertura


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
