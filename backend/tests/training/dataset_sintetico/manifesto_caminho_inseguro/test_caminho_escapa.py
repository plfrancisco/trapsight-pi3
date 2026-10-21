"""Verifica que o manifesto não pode acessar arquivos fora do catálogo."""

from pathlib import Path

import pytest

from training.dataset_sintetico import load_sprite_catalog


def test_manifesto_rejeita_caminho_que_escapa_do_banco(
    tmp_path: Path,
    criar_catalogo_manifesto,
) -> None:
    """Rejeita caminhos relativos que resolvem fora da raiz do banco."""
    catalogo = criar_catalogo_manifesto(
        tmp_path / "catalogo",
        caminho_pequeno="../x.png",
    )

    with pytest.raises(ValueError, match="escapa do banco"):
        load_sprite_catalog(catalogo)
