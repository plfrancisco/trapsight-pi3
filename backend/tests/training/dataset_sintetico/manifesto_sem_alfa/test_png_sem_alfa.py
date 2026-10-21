"""Verifica se cada sprite PNG declara um canal alfa."""

from pathlib import Path

import pytest

from training.dataset_sintetico import load_sprite_catalog


def test_manifesto_rejeita_png_sem_canal_alfa(
    tmp_path: Path,
    criar_catalogo_manifesto,
) -> None:
    """Rejeita sprites opacos sem um canal de transparência alfa."""
    catalogo = criar_catalogo_manifesto(tmp_path / "catalogo", alfa_medio=False)

    with pytest.raises(ValueError, match="canal alfa"):
        load_sprite_catalog(catalogo)
