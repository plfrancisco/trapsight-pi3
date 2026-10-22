"""Fixtures dos cenários de demonstração."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from sqlalchemy import select
from sqlalchemy.orm import Session

import src.seed_demo as seed_demo
from src.entities import ModeloArmadilha
from training.dataset_sintetico import SpriteCatalogado, load_sprite_catalog

DATA_REFERENCIA = date(2026, 10, 21)


@pytest.fixture
def sprites_seed(tmp_path: Path) -> tuple[SpriteCatalogado, ...]:
    """Cria um catálogo local com formas de todos os tamanhos."""
    raiz = tmp_path / "sprites"
    diretorio_insetos = raiz / "insetos"
    diretorio_insetos.mkdir(parents=True)
    registros = []
    formas = (
        ("pequeno", "pequeno.png", (8, 10, 56, 38), "elipse"),
        ("medio", "medio.png", (7, 8, 57, 40), "poligono"),
        ("grande", "grande.png", (5, 7, 59, 41), "retangulo"),
    )
    for categoria, nome, caixa, formato in formas:
        imagem = Image.new("RGBA", (64, 48), (0, 0, 0, 0))
        desenho = ImageDraw.Draw(imagem)
        if formato == "elipse":
            desenho.ellipse(caixa, fill=(43, 35, 28, 255))
        elif formato == "poligono":
            desenho.polygon(
                ((5, 25), (22, 7), (43, 12), (59, 29), (35, 41), (13, 38)),
                fill=(34, 42, 27, 255),
            )
        else:
            desenho.rectangle(caixa, fill=(52, 38, 24, 255))
        arquivo = f"insetos/{nome}"
        imagem.save(raiz / arquivo)
        registros.append(
            {
                "arquivo": arquivo,
                "categoria": categoria,
                "grupo": "mosca",
                "autor": "autor de teste",
                "fonte": "sprite-sintetico-de-teste",
                "licenca": "CC0-1.0",
                "fragmentado": categoria == "medio",
            }
        )
    (raiz / "manifest.json").write_text(
        json.dumps({"sprites": registros}),
        encoding="utf-8",
    )
    return load_sprite_catalog(raiz)


@pytest.fixture
def modelo_stickfly(session: Session) -> ModeloArmadilha:
    """Devolve o modelo cadastrado pela migration do catálogo."""
    modelo = session.scalars(
        select(ModeloArmadilha).where(ModeloArmadilha.codigo == seed_demo.CODIGO_MODELO)
    ).one()
    return modelo


@pytest.fixture
def data_seed(monkeypatch: pytest.MonkeyPatch) -> date:
    """Fixa a data do relógio para conferir a cronologia relativa."""
    monkeypatch.setattr(seed_demo, "data_atual", lambda: DATA_REFERENCIA)
    return DATA_REFERENCIA


@pytest.fixture
def executar_seed(tmp_path: Path, sprites_seed: tuple[SpriteCatalogado, ...]):
    """Cria os registros com arquivos isolados no diretório temporário."""

    def executar(session: Session):
        return seed_demo.criar_seed_demo(
            session,
            diretorio_uploads=tmp_path / "uploads",
            sprites=sprites_seed,
            resolucao=(320, 240),
        )

    return executar
