"""Valida a importação de sprites sem depender das bibliotecas locais."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from training.dataset_sintetico import load_sprite_catalog
from training.importar_sprites_reais import converter_catalogo


@pytest.fixture
def fontes_reais_teste(tmp_path: Path) -> dict[str, Path]:
    """Cria arquivos RGBA pequenos com metadados mínimos de procedência."""
    raiz_ums = tmp_path / "sprites-ums"
    raiz_amazonia = tmp_path / "sprites-amazonia"
    (raiz_ums / "png").mkdir(parents=True)
    (raiz_amazonia / "png").mkdir(parents=True)
    registros_ums = []
    for indice, tamanho in enumerate((20, 44, 100), start=1):
        identificador = f"ums-{indice}"
        imagem = Image.new("RGBA", (tamanho, tamanho // 2), (0, 0, 0, 0))
        ImageDraw.Draw(imagem).ellipse(
            (1, 1, tamanho - 2, tamanho // 2 - 2), fill=(40, 35, 30, 255)
        )
        imagem.save(raiz_ums / "png" / f"{identificador}.png")
        registros_ums.append(
            {
                "id": identificador,
                "classe": ("Diptera", "Psocoptera", "Hemiptera")[indice - 1],
                "largura": tamanho,
                "altura": tamanho // 2,
                "escala": 0.5,
                "area_px": tamanho * (tamanho // 2),
            }
        )
    (raiz_ums / "meta.json").write_text(json.dumps(registros_ums), encoding="utf-8")

    imagem_amazonia = Image.new("RGBA", (32, 24), (0, 0, 0, 0))
    ImageDraw.Draw(imagem_amazonia).ellipse((2, 2, 30, 22), fill=(40, 35, 30, 255))
    imagem_amazonia.save(raiz_amazonia / "png" / "amazon-1.png")
    (raiz_amazonia / "meta_filtrado.json").write_text(
        json.dumps([{"id": "amazon-1", "classe": "Hymenoptera", "area_px": 200}]),
        encoding="utf-8",
    )
    meta_ums = tmp_path / "ums-source.json"
    meta_ums.write_text(
        json.dumps(
            {
                "doi": "10.6084/m9.figshare.28280792.v1",
                "license": {"name": "CC BY 4.0"},
                "authors": [{"full_name": "Autoria UMS"}],
            }
        ),
        encoding="utf-8",
    )
    return {
        "ums": raiz_ums,
        "amazonia": raiz_amazonia,
        "meta_ums": meta_ums,
        "saida": tmp_path / "catalogo",
    }


def _importar(fontes: dict[str, Path], **alteracoes: object) -> dict[str, object]:
    opcoes: dict[str, object] = {
        "diretorio_ums": fontes["ums"],
        "manifesto_ums": fontes["ums"] / "meta.json",
        "metadados_ums": fontes["meta_ums"],
        "diretorio_amazonia": fontes["amazonia"],
        "manifesto_amazonia": fontes["amazonia"] / "meta_filtrado.json",
        "saida": fontes["saida"],
        "semente": 20261021,
        "fonte_amazonia": "https://doi.org/10.6084/m9.figshare.28688198",
        "licenca_amazonia": "CC BY 4.0",
        "autor_amazonia": "Autoria Amazônia",
    }
    opcoes.update(alteracoes)
    return converter_catalogo(**opcoes)  # type: ignore[arg-type]


def test_importacao_cataloga_escala_fisica_e_grupos(
    fontes_reais_teste: dict[str, Path],
) -> None:
    """Converte as duas fontes, estima escalas e mantém créditos no manifesto."""
    manifesto = _importar(fontes_reais_teste)
    sprites = manifesto["sprites"]
    assert isinstance(sprites, list)

    ums = sprites[0]
    amazonia = sprites[-1]
    assert ums["tamanho_mm"] == pytest.approx(20 / 23.62)
    assert ums["px_por_mm"] == pytest.approx(23.62)
    assert ums["grupo"] == "mosquito"
    assert ums["origem_escala"] == "medida"
    assert amazonia["grupo"] in {"formiga", "vespa"}
    assert amazonia["origem_escala"] == "estimada_por_grupo_ums"
    assert amazonia["fonte"].endswith("28688198")
    assert amazonia["licenca"] == "CC BY 4.0"
    assert (fontes_reais_teste["saida"] / "manifest.json").is_file()
    assert len(load_sprite_catalog(fontes_reais_teste["saida"])) == 4


def test_importacao_recusa_procedencia_ausente(
    fontes_reais_teste: dict[str, Path],
) -> None:
    """Não grava sprites sem atribuição de fonte, licença e autoria."""
    with pytest.raises(ValueError, match="fonte pública"):
        _importar(fontes_reais_teste, fonte_amazonia=" ")
    assert not fontes_reais_teste["saida"].exists()


def test_importacao_nao_sobrescreve_catalogo_existente(
    fontes_reais_teste: dict[str, Path],
) -> None:
    """Protege arquivos preexistentes na pasta de destino."""
    fontes_reais_teste["saida"].mkdir()
    marcador = fontes_reais_teste["saida"] / "preservar.txt"
    marcador.write_text("fora do catálogo", encoding="utf-8")

    with pytest.raises(FileExistsError, match="não está vazio"):
        _importar(fontes_reais_teste)

    assert marcador.read_text(encoding="utf-8") == "fora do catálogo"
