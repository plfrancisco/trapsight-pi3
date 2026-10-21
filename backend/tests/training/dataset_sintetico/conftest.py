"""Fixtures compartilhadas pelos testes do dataset sintético."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from training.dataset_sintetico import (
    ConfiguracaoDataset,
    LIMITE_SPRITES_POR_AMOSTRA,
    SpriteCatalogado,
    generate_dataset,
    load_sprite_catalog,
)


@pytest.fixture
def sprites_catalogados(tmp_path: Path) -> tuple[SpriteCatalogado, ...]:
    """Cria sprites de teste com alfa e procedência declarada."""
    diretorio = tmp_path / "sprites"
    (diretorio / "insetos").mkdir(parents=True)
    registros = []
    for categoria, nome, formato in (
        ("pequeno", "pequeno.png", "elipse"),
        ("medio", "medio.png", "poligono"),
        ("grande", "grande.png", "retangulo"),
    ):
        caminho_relativo = f"insetos/{nome}"
        imagem = Image.new("RGBA", (64, 48), (0, 0, 0, 0))
        desenho = ImageDraw.Draw(imagem)
        if formato == "elipse":
            desenho.ellipse((8, 10, 56, 38), fill=(43, 35, 28, 255))
        elif formato == "poligono":
            desenho.polygon(
                ((5, 25), (22, 7), (43, 12), (59, 29), (35, 41), (13, 38)),
                fill=(34, 42, 27, 255),
            )
        else:
            desenho.rectangle((7, 8, 57, 40), fill=(52, 38, 24, 255))
        imagem.save(diretorio / caminho_relativo, format="PNG")
        registros.append(
            {
                "arquivo": caminho_relativo,
                "categoria": categoria,
                "grupo": "mosca",
                "autor": "autor de teste",
                "fonte": "conjunto-sintetico-de-teste",
                "licenca": "CC0-1.0",
                "fragmentado": categoria == "medio",
            }
        )
    (diretorio / "manifest.json").write_text(
        json.dumps({"sprites": registros}),
        encoding="utf-8",
    )
    return load_sprite_catalog(diretorio)


@pytest.fixture
def gerar_dataset_teste(
    sprites_catalogados: tuple[SpriteCatalogado, ...],
) -> Callable[..., list[dict[str, object]]]:
    """Gera um dataset pequeno com configuração comum aos testes."""

    def gerar(
        diretorio: Path,
        quantidade: int,
        semente: int = 20261021,
        limite_sprites: int = LIMITE_SPRITES_POR_AMOSTRA,
    ) -> list[dict[str, object]]:
        configuracao = ConfiguracaoDataset(
            diretorio_saida=diretorio,
            semente=semente,
            idade_maxima_dias=90,
            quantidade=quantidade,
            resolucao=(320, 240),
            limite_sprites=limite_sprites,
        )
        return generate_dataset(configuracao, sprites_catalogados)

    return gerar


@pytest.fixture
def criar_catalogo_manifesto() -> Callable[..., Path]:
    """Cria um catálogo temporário com variações controladas do manifesto."""

    def criar(
        diretorio: Path,
        *,
        caminho_pequeno: str = "insetos/pequeno.png",
        categoria_media: str = "medio",
        alfa_medio: bool = True,
        duplicar_arquivo: bool = False,
        incluir_fragmento: bool = True,
    ) -> Path:
        pasta_insetos = diretorio / "insetos"
        pasta_insetos.mkdir(parents=True)
        registros = []
        sprites = (
            ("pequeno", "pequeno.png", (8, 10, 56, 38), "elipse"),
            ("medio", "medio.png", (7, 8, 57, 40), "retangulo"),
            ("grande", "grande.png", (5, 7, 59, 41), "retangulo"),
        )
        for categoria, nome, caixa, formato in sprites:
            modo = "RGBA" if categoria != "medio" or alfa_medio else "RGB"
            cor = (48, 42, 30, 255) if modo == "RGBA" else (48, 42, 30)
            imagem = Image.new(
                modo, (64, 48), (0, 0, 0, 0) if modo == "RGBA" else (0, 0, 0)
            )
            desenho = ImageDraw.Draw(imagem)
            if formato == "elipse":
                desenho.ellipse(caixa, fill=cor)
            else:
                desenho.rectangle(caixa, fill=cor)
            imagem.save(pasta_insetos / nome, format="PNG")
            arquivo = caminho_pequeno if categoria == "pequeno" else f"insetos/{nome}"
            categoria_manifesto = categoria_media if categoria == "medio" else categoria
            registros.append(
                {
                    "arquivo": arquivo,
                    "categoria": categoria_manifesto,
                    "grupo": "mosca",
                    "autor": "autor de teste",
                    "fonte": "conjunto-sintetico-de-teste",
                    "licenca": "CC0-1.0",
                    "fragmentado": categoria == "medio" and incluir_fragmento,
                }
            )
        if duplicar_arquivo:
            registros.append(dict(registros[0]))
        (diretorio / "manifest.json").write_text(
            json.dumps({"sprites": registros}),
            encoding="utf-8",
        )
        return diretorio

    return criar
