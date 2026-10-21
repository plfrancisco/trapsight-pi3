"""Fixtures para conjuntos COCO pequenos e reprodutíveis."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from PIL import Image, ImageDraw


@pytest.fixture
def criar_conjunto_coco(
    tmp_path: Path,
) -> Callable[..., Path]:
    """Cria imagens e anotações COCO com polígonos definidos pelo teste."""

    def criar(
        diretorio: Path,
        segmentacoes: list[dict[str, object]],
        tamanho: tuple[int, int] = (128, 128),
    ) -> Path:
        pasta_imagens = diretorio / "imagens"
        pasta_imagens.mkdir(parents=True)
        imagens = []
        anotacoes = []
        for indice, especificacao in enumerate(segmentacoes):
            nome_arquivo = f"imagens/imagem_{indice:03d}.png"
            imagem = Image.new("RGB", tamanho, (220, 215, 185))
            desenho = ImageDraw.Draw(imagem)
            segmentacao = especificacao.get("segmentation")
            if isinstance(segmentacao, list) and segmentacao:
                poligonos = (
                    [segmentacao]
                    if all(isinstance(valor, (int, float)) for valor in segmentacao)
                    else segmentacao
                )
                for poligono in poligonos:
                    if isinstance(poligono, list):
                        pontos = list(zip(poligono[::2], poligono[1::2], strict=True))
                        if len(pontos) >= 3:
                            desenho.polygon(pontos, fill=(45, 35, 24))
            imagem.save(diretorio / nome_arquivo, format="PNG")
            imagens.append(
                {
                    "id": indice + 1,
                    "file_name": especificacao.get("file_name", nome_arquivo),
                    "width": tamanho[0],
                    "height": tamanho[1],
                }
            )
            anotacoes.append(
                {
                    "id": indice + 1,
                    "image_id": indice + 1,
                    "category_id": 1,
                    "segmentation": segmentacao,
                }
            )
        documento = {
            "images": imagens,
            "annotations": anotacoes,
            "categories": [{"id": 1, "name": "Musca domestica"}],
        }
        (diretorio / "anotacoes.coco.json").write_text(
            json.dumps(documento),
            encoding="utf-8",
        )
        return diretorio

    return criar
