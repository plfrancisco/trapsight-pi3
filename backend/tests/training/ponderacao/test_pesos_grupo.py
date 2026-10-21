"""Valida a ponderação taxonômica e os pesos gravados por amostra."""

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from training.dataset_sintetico import (
    GRUPOS_INSETOS,
    PESOS_GRUPO_PADRAO,
    ConfiguracaoDataset,
    SpriteCatalogado,
    _normalizar_pesos_grupo,
    generate_dataset,
)


def _criar_sprites(diretorio: Path) -> tuple[SpriteCatalogado, ...]:
    sprites = []
    for categoria in ("pequeno", "medio", "grande"):
        imagem = Image.new("RGBA", (40, 32), (0, 0, 0, 0))
        ImageDraw.Draw(imagem).ellipse((4, 4, 36, 28), fill=(40, 35, 25, 255))
        sprites.append(
            SpriteCatalogado(
                imagem=imagem,
                categoria=categoria,
                grupo="mosca",
                arquivo=f"{categoria}.png",
                autor="Autoria de teste",
                fonte="origem de teste",
                licenca="cc0",
                especie="Musca domestica",
                fragmentado=categoria == "medio",
            )
        )
    return tuple(sprites)


def test_pesos_padrao_separam_voadores_e_insetos_rasteiros() -> None:
    """Os grupos voadores recebem 70% e os rasteiros recebem 30%."""
    pesos = _normalizar_pesos_grupo(set(GRUPOS_INSETOS), PESOS_GRUPO_PADRAO)
    peso_voadores = sum(pesos[grupo] for grupo in ("mosca", "mosquito", "mariposa"))
    peso_rasteiros = sum(pesos[grupo] for grupo in ("formiga", "barata", "besouro"))

    assert peso_voadores == pytest.approx(0.70)
    assert peso_rasteiros == pytest.approx(0.30)


def test_pesos_efetivos_ficam_nos_metadados_de_cada_imagem(
    tmp_path: Path,
) -> None:
    """Persiste por amostra os pesos realmente disponíveis no catálogo."""
    configuracao = ConfiguracaoDataset(
        diretorio_saida=tmp_path / "dataset",
        semente=83,
        idade_maxima_dias=90,
        quantidade=3,
        resolucao=(160, 120),
        limite_sprites=30,
        pesos_grupo={"mosca": 2.0, "besouro": 1.0},
    )

    registros = generate_dataset(configuracao, _criar_sprites(tmp_path))

    assert len(registros) == 3
    assert all(registro["pesos_grupo"] == {"mosca": 1.0} for registro in registros)
