"""Valida os arquivos e os registros do catálogo de sprites."""

from __future__ import annotations

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


def test_manifesto_rejeita_png_sem_canal_alfa(
    tmp_path: Path,
    criar_catalogo_manifesto,
) -> None:
    """Rejeita sprites opacos sem um canal de transparência alfa."""
    catalogo = criar_catalogo_manifesto(tmp_path / "catalogo", alfa_medio=False)

    with pytest.raises(ValueError, match="canal alfa"):
        load_sprite_catalog(catalogo)


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
