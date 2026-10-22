"""Valida os arquivos e os registros do catálogo de sprites."""

from __future__ import annotations

import json
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


def test_manifesto_aceita_banco_sem_fragmentos(
    tmp_path: Path,
    criar_catalogo_manifesto,
) -> None:
    """Aceita bibliotecas de sprites reais sem recortes fragmentados."""
    catalogo = criar_catalogo_manifesto(
        tmp_path / "catalogo",
        incluir_fragmento=False,
    )

    sprites = load_sprite_catalog(catalogo)

    assert len(sprites) == 3
    assert not any(sprite.fragmentado for sprite in sprites)


def test_manifesto_preserva_escala_fisica_opcional(
    tmp_path: Path,
    criar_catalogo_manifesto,
) -> None:
    """Carrega tamanho físico sem exigir esses campos em manifestos antigos."""
    catalogo = criar_catalogo_manifesto(tmp_path / "catalogo")
    caminho = catalogo / "manifest.json"
    registros = json.loads(caminho.read_text(encoding="utf-8"))
    registros["sprites"][0].update(
        {
            "tamanho_mm": 2.1,
            "px_por_mm": 23.62,
            "classe_origem": "Diptera",
            "origem_escala": "medida",
        }
    )
    caminho.write_text(json.dumps(registros), encoding="utf-8")

    sprites = load_sprite_catalog(catalogo)

    assert sprites[0].tamanho_mm == 2.1
    assert sprites[0].px_por_mm == 23.62
    assert sprites[0].classe_origem == "Diptera"
    assert sprites[0].origem_escala == "medida"
    assert sprites[1].tamanho_mm is None
