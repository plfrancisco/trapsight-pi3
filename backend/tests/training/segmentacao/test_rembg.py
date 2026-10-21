"""Valida seleção de componente e remoção de fundo das fotos."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType

from PIL import Image, ImageDraw

from training.preparar_sprites import (
    ConfiguracaoPreparo,
    _borda_parece_fundo,
    _cor_fundo_borda,
    _maior_componente_conectado,
    prepare_sprite_bank,
)


def test_mantem_somente_o_maior_componente_conectado() -> None:
    """Remove pontos isolados e mantém a silhueta de maior área."""
    mascara = Image.new("L", (30, 24), 0)
    desenho = ImageDraw.Draw(mascara)
    desenho.rectangle((2, 3, 14, 16), fill=255)
    desenho.rectangle((23, 3, 25, 5), fill=255)

    componente = _maior_componente_conectado(mascara)

    assert componente.histogram()[255] == 13 * 14
    assert componente.getpixel((24, 4)) == 0


def test_descarta_borda_do_recorte_parecida_com_o_fundo() -> None:
    """Detecta fundo do quadro original que permaneceu junto à silhueta."""
    original = Image.new("RGB", (40, 40), (110, 145, 180))
    recorte = Image.new("RGB", (20, 20), (110, 145, 180))
    ImageDraw.Draw(recorte).rectangle((4, 4, 15, 15), fill=(35, 27, 19))
    mascara = Image.new("L", (20, 20), 255)

    assert _borda_parece_fundo(recorte, mascara, _cor_fundo_borda(original))


def test_rembg_grava_sprite_rgba_com_procedencia_e_relatorio(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Aplica a máscara, recorta as fotos e conserva autor, licença e grupo."""
    entrada = tmp_path / "dados"
    pasta_fotos = entrada / "inaturalist" / "fotos" / "mosca"
    pasta_fotos.mkdir(parents=True)
    registros = []
    mascaras = []
    for indice in range(2):
        caminho = pasta_fotos / f"{indice + 1}.png"
        imagem = Image.new("RGB", (64, 64), (220, 220, 220))
        ImageDraw.Draw(imagem).ellipse(
            (20, 20, 44, 44),
            fill=(45 + indice * 20, 30, 20),
        )
        imagem.save(caminho)
        mascara = Image.new("L", (64, 64), 0)
        ImageDraw.Draw(mascara).ellipse((20, 20, 44, 44), fill=255)
        mascaras.append(mascara)
        registros.append(
            {
                "id_observacao": 100 + indice,
                "id_foto": 200 + indice,
                "arquivo": f"inaturalist/fotos/mosca/{indice + 1}.png",
                "url": f"https://inaturalist-open-data.s3.amazonaws.com/{indice}.jpg",
                "autor": f"Autor {indice}",
                "licenca": "cc-by",
                "taxon": "Musca domestica",
                "grupo": "mosca",
            }
        )
    pasta_manifesto = entrada / "inaturalist"
    pasta_manifesto.mkdir(exist_ok=True)
    (pasta_manifesto / "manifesto_coleta.json").write_text(
        json.dumps({"fotos": registros}),
        encoding="utf-8",
    )

    modulo_rembg = ModuleType("rembg")
    modulo_rembg.new_session = lambda nome: nome
    chamadas = iter(mascaras)
    modulo_rembg.remove = lambda imagem, session, only_mask: next(chamadas)
    monkeypatch.setitem(sys.modules, "rembg", modulo_rembg)

    saida = entrada / "sprites"
    relatorio = prepare_sprite_bank(
        ConfiguracaoPreparo(
            entrada=entrada,
            saida=saida,
            semente=8,
            area_minima_pixels=1,
            minimo_sprites=3,
            minimo_por_grupo=0,
        )
    )
    manifesto = json.loads((saida / "manifest.json").read_text(encoding="utf-8"))

    assert relatorio["fotos_baixadas"] == 2
    assert relatorio["recortes_aceitos"] == 2
    assert relatorio["sprites_por_grupo"]["mosca"] == 3
    assert all(
        registro["grupo"] == "mosca" and registro["autor"].startswith("Autor ")
        for registro in manifesto["sprites"]
    )
    assert all(registro["licenca"] == "cc-by" for registro in manifesto["sprites"])
    with Image.open(saida / manifesto["sprites"][0]["arquivo"]) as sprite:
        assert sprite.mode == "RGBA"
        assert sprite.getchannel("A").getbbox() is not None
