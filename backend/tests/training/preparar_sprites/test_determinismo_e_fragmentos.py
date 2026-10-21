"""Verifica a reprodutibilidade e os recortes parciais de insetos."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from training.preparar_sprites import ConfiguracaoPreparo, prepare_sprite_bank


def _retangulo(x: int, y: int, largura: int, altura: int) -> list[int]:
    return [x, y, x + largura, y, x + largura, y + altura, x, y + altura]


def _configuracao(entrada: Path, saida: Path) -> ConfiguracaoPreparo:
    return ConfiguracaoPreparo(
        entrada=entrada,
        saida=saida,
        fonte="fonte de teste",
        licenca="CC-BY-4.0",
        semente=20261021,
        minimo_sprites=7,
        minimo_por_grupo=0,
    )


def test_mesma_entrada_e_semente_produzem_banco_byte_a_byte_identico(
    tmp_path: Path,
    criar_conjunto_coco,
) -> None:
    """Compara os bytes de imagens, manifesto e relatório em duas execuções."""
    entrada = criar_conjunto_coco(
        tmp_path / "coco",
        [
            {"segmentation": [_retangulo(10, 10, 10, 10)]},
            {"segmentation": [_retangulo(10, 10, 20, 20)]},
            {"segmentation": [_retangulo(10, 10, 30, 20)]},
            {"segmentation": [_retangulo(10, 10, 12, 12)]},
            {"segmentation": [_retangulo(10, 10, 22, 18)]},
            {"segmentation": [_retangulo(10, 10, 31, 20)]},
        ],
    )
    primeira = tmp_path / "primeira"
    segunda = tmp_path / "segunda"

    primeiro_relatorio = prepare_sprite_bank(_configuracao(entrada, primeira))
    segundo_relatorio = prepare_sprite_bank(_configuracao(entrada, segunda))

    arquivos_primeiros = {
        caminho.relative_to(primeira): caminho.read_bytes()
        for caminho in primeira.rglob("*")
        if caminho.is_file()
    }
    arquivos_segundos = {
        caminho.relative_to(segunda): caminho.read_bytes()
        for caminho in segunda.rglob("*")
        if caminho.is_file()
    }
    assert arquivos_primeiros == arquivos_segundos
    assert primeiro_relatorio == segundo_relatorio


def test_gera_fragmentos_com_area_minima_e_marca_manifesto(
    tmp_path: Path,
    criar_conjunto_coco,
) -> None:
    """Cria fragmentos opacos e declara sua origem no manifesto."""
    entrada = criar_conjunto_coco(
        tmp_path / "coco",
        [
            {"segmentation": [_retangulo(10, 10, 10, 10)]},
            {"segmentation": [_retangulo(10, 10, 20, 20)]},
            {"segmentation": [_retangulo(10, 10, 30, 20)]},
            {"segmentation": [_retangulo(10, 10, 12, 12)]},
            {"segmentation": [_retangulo(10, 10, 22, 18)]},
            {"segmentation": [_retangulo(10, 10, 31, 20)]},
        ],
    )
    saida = tmp_path / "sprites"
    relatorio = prepare_sprite_bank(_configuracao(entrada, saida))
    manifesto = json.loads((saida / "manifest.json").read_text(encoding="utf-8"))
    fragmentos = [
        registro for registro in manifesto["sprites"] if registro["fragmentado"]
    ]

    assert relatorio["numero_fragmentos"] == len(fragmentos) == 1
    for registro in fragmentos:
        with Image.open(saida / registro["arquivo"]) as imagem:
            alfa = imagem.getchannel("A")
            assert alfa.histogram()[255] >= 50
