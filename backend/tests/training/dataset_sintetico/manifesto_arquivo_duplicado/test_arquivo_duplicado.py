"""Verifica que o manifesto não repete o caminho de um sprite."""

from pathlib import Path

import pytest

from training.dataset_sintetico import load_sprite_catalog


def test_manifesto_rejeita_arquivo_duplicado(
    tmp_path: Path,
    criar_catalogo_manifesto,
) -> None:
    """Rejeita um arquivo declarado mais de uma vez no catálogo."""
    catalogo = criar_catalogo_manifesto(
        tmp_path / "catalogo",
        duplicar_arquivo=True,
    )

    with pytest.raises(ValueError, match="aparece mais de uma vez"):
        load_sprite_catalog(catalogo)
