"""Verifica que o catálogo contém pelo menos um fragmento de inseto."""

from pathlib import Path

import pytest

from training.dataset_sintetico import load_sprite_catalog


def test_manifesto_rejeita_banco_sem_fragmentos(
    tmp_path: Path,
    criar_catalogo_manifesto,
) -> None:
    """Rejeita bancos sem nenhum sprite marcado como fragmentado."""
    catalogo = criar_catalogo_manifesto(
        tmp_path / "catalogo",
        incluir_fragmento=False,
    )

    with pytest.raises(ValueError, match="fragmentos de insetos"):
        load_sprite_catalog(catalogo)
