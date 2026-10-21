"""Verifica a validação das categorias declaradas no manifesto."""

from pathlib import Path

import pytest

from training.dataset_sintetico import load_sprite_catalog


def test_manifesto_rejeita_categoria_desconhecida(
    tmp_path: Path,
    criar_catalogo_manifesto,
) -> None:
    """Rejeita categorias fora dos três grupos de tamanho aceitos."""
    catalogo = criar_catalogo_manifesto(
        tmp_path / "catalogo",
        categoria_media="gigante",
    )

    with pytest.raises(ValueError, match="pequeno, medio ou grande"):
        load_sprite_catalog(catalogo)
