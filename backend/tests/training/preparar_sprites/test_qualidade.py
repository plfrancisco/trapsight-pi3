"""Verifica os filtros de área e complexidade do contorno."""

import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from training.preparar_sprites import ConfiguracaoPreparo, prepare_sprite_bank


def _retangulo(x: int, y: int, largura: int, altura: int) -> list[int]:
    return [x, y, x + largura, y, x + largura, y + altura, x, y + altura]


def test_descarta_mascara_abaixo_da_area_minima(
    tmp_path: Path,
    criar_conjunto_coco,
) -> None:
    """Registra como minúsculo um recorte abaixo do limiar configurado."""
    entrada = criar_conjunto_coco(
        tmp_path / "coco",
        [
            {"segmentation": [_retangulo(10, 10, 7, 7)]},
            {"segmentation": [_retangulo(10, 10, 20, 20)]},
            {"segmentation": [_retangulo(10, 10, 30, 20)]},
        ],
    )
    configuracao = ConfiguracaoPreparo(
        entrada=entrada,
        saida=tmp_path / "sprites",
        fonte="fonte de teste",
        licenca="CC-BY-4.0",
        semente=4,
        area_minima_pixels=100,
        minimo_sprites=3,
        minimo_por_grupo=0,
    )

    relatorio = prepare_sprite_bank(configuracao)

    assert relatorio["descartados_por_motivo"]["area_minima"] == 1
    assert relatorio["recortes_aceitos"] == 2


def test_descarta_contorno_muito_serrilhado(
    tmp_path: Path,
    criar_conjunto_coco,
) -> None:
    """Rejeita uma silhueta cuja borda excede o perímetro do casco convexo."""
    pontos = [10, 70]
    for x in range(10, 91, 2):
        pontos.extend((x, 20 if (x // 2) % 2 else 40))
    pontos.extend((90, 100, 10, 100))
    entrada = criar_conjunto_coco(
        tmp_path / "coco",
        [
            {"segmentation": [pontos]},
            {"segmentation": [_retangulo(10, 10, 20, 20)]},
            {"segmentation": [_retangulo(10, 10, 30, 20)]},
        ],
    )
    configuracao = ConfiguracaoPreparo(
        entrada=entrada,
        saida=tmp_path / "sprites",
        fonte="fonte de teste",
        licenca="CC-BY-4.0",
        semente=4,
        limite_serrilhado=1.5,
        minimo_sprites=3,
        minimo_por_grupo=0,
    )

    relatorio = prepare_sprite_bank(configuracao)

    assert relatorio["descartados_por_motivo"]["bordas_serrilhadas"] == 1
    assert relatorio["recortes_aceitos"] == 2


def test_descarta_borda_com_cor_semelhante_ao_fundo_da_foto(
    tmp_path: Path,
    criar_conjunto_coco,
) -> None:
    """Descarta polígonos amplos que incluem fundo da imagem original."""
    entrada = criar_conjunto_coco(
        tmp_path / "coco",
        [
            {"segmentation": [_retangulo(10, 10, 50, 50)]},
            {"segmentation": [_retangulo(10, 10, 20, 20)]},
            {"segmentation": [_retangulo(10, 10, 30, 20)]},
            {"segmentation": [_retangulo(10, 10, 24, 30)]},
        ],
    )
    imagem_fonte = entrada / "imagens" / "imagem_000.png"
    imagem = Image.new("RGB", (128, 128), (220, 215, 185))
    ImageDraw.Draw(imagem).ellipse((29, 29, 42, 42), fill=(45, 35, 24))
    imagem.save(imagem_fonte)

    relatorio = prepare_sprite_bank(
        ConfiguracaoPreparo(
            entrada=entrada,
            saida=tmp_path / "sprites",
            fonte="fonte de teste",
            licenca="CC-BY-4.0",
            semente=4,
            minimo_sprites=4,
            minimo_por_grupo=0,
        )
    )

    assert relatorio["descartados_por_motivo"]["fundo_residual"] == 1


def test_banco_falha_quando_um_grupo_nao_atinge_o_minimo(
    tmp_path: Path,
    criar_conjunto_coco,
) -> None:
    """Não publica um catálogo sem a diversidade mínima de grupos."""
    entrada = criar_conjunto_coco(
        tmp_path / "coco",
        [
            {"segmentation": [_retangulo(10, 10, 20, 20)]},
            {"segmentation": [_retangulo(10, 10, 30, 20)]},
            {"segmentation": [_retangulo(10, 10, 24, 30)]},
        ],
    )
    saida = tmp_path / "sprites"
    configuracao = ConfiguracaoPreparo(
        entrada=entrada,
        saida=saida,
        fonte="fonte de teste",
        licenca="CC-BY-4.0",
        semente=4,
        minimo_sprites=3,
    )

    with pytest.raises(ValueError, match="20 sprites inteiros por grupo"):
        prepare_sprite_bank(configuracao)

    assert not saida.exists()
    relatorio = json.loads(
        (tmp_path / "relatorio_preparo.json").read_text(encoding="utf-8")
    )
    assert relatorio["metas_atingidas"] is False
    assert "ao menos 20 sprites inteiros por grupo" in relatorio["motivos_falha"][0]
