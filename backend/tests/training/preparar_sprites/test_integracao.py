"""Valida os requisitos mínimos e a integração com o gerador de dataset."""

from pathlib import Path

import pytest

from training.dataset_sintetico import (
    ConfiguracaoDataset,
    generate_dataset,
    load_sprite_catalog,
)
from training.preparar_sprites import ConfiguracaoPreparo, prepare_sprite_bank


def _segmentacoes(quantidade: int = 6) -> list[dict[str, object]]:
    formas = ((10, 10), (20, 20), (30, 20), (12, 12), (22, 18), (31, 20))
    return [
        {
            "segmentation": [
                [10, 10, 10 + largura, 10, 10 + largura, 10 + altura, 10, 10 + altura]
            ]
        }
        for largura, altura in formas[:quantidade]
    ]


def test_recusa_banco_abaixo_da_meta_sem_publicar_saida(
    tmp_path: Path,
    criar_conjunto_coco,
) -> None:
    """Falha com mensagem explícita e sem deixar catálogo parcial."""
    entrada = criar_conjunto_coco(
        tmp_path / "coco",
        _segmentacoes(2),
    )
    saida = tmp_path / "sprites-incompletos"
    configuracao = ConfiguracaoPreparo(
        entrada=entrada,
        saida=saida,
        fonte="fonte de teste",
        licenca="CC-BY-4.0",
        semente=8,
        minimo_sprites=4,
        minimo_por_grupo=0,
    )

    with pytest.raises(ValueError, match="mínimo configurado é 4"):
        prepare_sprite_bank(configuracao)

    assert not saida.exists()


def test_banco_preparado_alimenta_o_gerador_de_dataset(
    tmp_path: Path,
    criar_conjunto_coco,
) -> None:
    """Carrega o catálogo produzido e gera doze amostras sintéticas."""
    entrada = criar_conjunto_coco(tmp_path / "coco", _segmentacoes())
    saida_sprites = tmp_path / "sprites"
    prepare_sprite_bank(
        ConfiguracaoPreparo(
            entrada=entrada,
            saida=saida_sprites,
            fonte="fonte de teste",
            licenca="CC-BY-4.0",
            semente=13,
            minimo_sprites=7,
            minimo_por_grupo=0,
        )
    )
    sprites = load_sprite_catalog(saida_sprites)
    registros = generate_dataset(
        ConfiguracaoDataset(
            diretorio_saida=tmp_path / "dataset",
            semente=13,
            idade_maxima_dias=90,
            quantidade=12,
            resolucao=(160, 120),
            limite_sprites=40,
        ),
        sprites,
    )

    assert len(sprites) == 7
    assert len(registros) == 12
    assert len(list((tmp_path / "dataset" / "imagens").glob("*.png"))) == 12
    assert len(list((tmp_path / "dataset" / "mascaras").glob("*.png"))) == 12
