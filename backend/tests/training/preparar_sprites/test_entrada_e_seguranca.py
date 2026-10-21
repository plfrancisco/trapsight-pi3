"""Valida caminhos, estruturas COCO e publicação da saída."""

import json
from pathlib import Path

import pytest
from PIL import Image

from training.preparar_sprites import ConfiguracaoPreparo, prepare_sprite_bank


def _retangulo(x: int, y: int, largura: int, altura: int) -> list[int]:
    return [x, y, x + largura, y, x + largura, y + altura, x, y + altura]


def _configuracao(entrada: Path, saida: Path, **opcoes: object) -> ConfiguracaoPreparo:
    opcoes.setdefault("minimo_sprites", 4)
    opcoes.setdefault("minimo_por_grupo", 0)
    return ConfiguracaoPreparo(
        entrada=entrada,
        saida=saida,
        fonte="https://example.org/dataset",
        licenca="CC-BY-4.0",
        semente=41,
        **opcoes,
    )


def test_converte_poligonos_e_escreve_manifesto_e_relatorio(
    tmp_path: Path,
    criar_conjunto_coco,
) -> None:
    """Grava recortes RGBA, metadados de licença e contagens por tamanho."""
    entrada = criar_conjunto_coco(
        tmp_path / "coco",
        [
            {"segmentation": [_retangulo(10, 10, 10, 10)]},
            {"segmentation": [_retangulo(10, 10, 20, 20)]},
            {"segmentation": [_retangulo(10, 10, 30, 20)]},
        ],
    )
    saida = tmp_path / "sprites"

    relatorio = prepare_sprite_bank(_configuracao(entrada, saida))

    assert relatorio["recortes_lidos"] == 3
    assert relatorio["sprites_aceitos"] == 4
    assert sum(relatorio["sprites_por_categoria"].values()) == 4
    assert (saida / "relatorio.json").is_file()
    assert (saida / "manifest.json").is_file()
    manifesto = json.loads((saida / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifesto["sprites"]) == 4
    assert all(
        {
            "arquivo",
            "categoria",
            "grupo",
            "autor",
            "fonte",
            "licenca",
            "fragmentado",
        }
        <= registro.keys()
        for registro in manifesto["sprites"]
    )
    assert relatorio["descartados_por_motivo"]["fundo_residual"] == 0
    with Image.open(saida / manifesto["sprites"][0]["arquivo"]) as imagem:
        assert imagem.mode == "RGBA"


def test_ignora_rle_e_anotacao_sem_poligono(
    tmp_path: Path,
    criar_conjunto_coco,
) -> None:
    """Conta RLE e segmentações ausentes sem interromper a conversão."""
    entrada = criar_conjunto_coco(
        tmp_path / "coco",
        [
            {"segmentation": [_retangulo(10, 10, 10, 10)]},
            {"segmentation": [_retangulo(10, 10, 20, 20)]},
            {"segmentation": [_retangulo(10, 10, 30, 20)]},
            {"segmentation": {"counts": "rle", "size": [128, 128]}},
            {"segmentation": None},
        ],
    )

    relatorio = prepare_sprite_bank(
        _configuracao(entrada, tmp_path / "sprites", minimo_sprites=4)
    )

    assert relatorio["recortes_lidos"] == 5
    assert relatorio["descartados_por_motivo"]["rle"] == 1
    assert relatorio["descartados_por_motivo"]["sem_poligono"] == 1


def test_descarta_recorte_duplicado(
    tmp_path: Path,
    criar_conjunto_coco,
) -> None:
    """Mantém uma cópia de cada sprite visualmente idêntico."""
    primeiro = {"segmentation": [_retangulo(10, 10, 10, 10)]}
    entrada = criar_conjunto_coco(
        tmp_path / "coco",
        [
            primeiro,
            {"segmentation": [_retangulo(10, 10, 20, 20)]},
            {"segmentation": [_retangulo(10, 10, 30, 20)]},
            primeiro,
        ],
    )

    relatorio = prepare_sprite_bank(_configuracao(entrada, tmp_path / "sprites"))

    assert relatorio["descartados_por_motivo"]["duplicado"] == 1
    assert relatorio["recortes_aceitos"] == 3


def test_rejeita_caminho_de_imagem_que_escapa_da_entrada(
    tmp_path: Path,
    criar_conjunto_coco,
) -> None:
    """Impede leitura de imagens referenciadas fora da raiz COCO."""
    entrada = criar_conjunto_coco(
        tmp_path / "coco",
        [{"segmentation": [_retangulo(10, 10, 20, 20)], "file_name": "../x.png"}],
    )

    with pytest.raises(ValueError, match="caminho escapa"):
        prepare_sprite_bank(_configuracao(entrada, tmp_path / "sprites"))


def test_nao_sobrescreve_diretorio_de_saida_nao_vazio(
    tmp_path: Path,
    criar_conjunto_coco,
) -> None:
    """Preserva arquivos existentes no destino indicado."""
    entrada = criar_conjunto_coco(
        tmp_path / "coco",
        [{"segmentation": [_retangulo(10, 10, 20, 20)]}],
    )
    saida = tmp_path / "sprites"
    saida.mkdir()
    marcador = saida / "manter.txt"
    marcador.write_text("conteudo", encoding="utf-8")

    with pytest.raises(FileExistsError, match="não está vazio"):
        prepare_sprite_bank(_configuracao(entrada, saida))

    assert marcador.read_text(encoding="utf-8") == "conteudo"
