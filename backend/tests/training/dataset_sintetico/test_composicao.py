"""Verifica a cobertura da placa e a independência dos distratores."""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

import training.dataset_sintetico as modulo
from training.dataset_sintetico import (
    SpriteCatalogado,
    create_plate_geometry,
    generate_sample,
)


def test_convergencia_das_tres_faixas_de_cobertura(
    tmp_path: Path,
    gerar_dataset_teste,
) -> None:
    """Gera amostras estratificadas e registra a taxa de alvo atingido."""
    registros = gerar_dataset_teste(
        tmp_path / "dataset",
        quantidade=30,
        semente=20261021,
    )
    contagens = {
        faixa: sum(registro["faixa_cobertura_alvo"] == faixa for registro in registros)
        for faixa in ("ok", "atencao", "trocar")
    }
    print(f"Amostras por faixa: {json.dumps(contagens, sort_keys=True)}")

    assert contagens == {"ok": 10, "atencao": 10, "trocar": 10}
    assert all(registro["alvo_atingido"] is True for registro in registros)
    assert all(
        abs(
            float(registro["percentual_cobertura_real"])
            - float(registro["percentual_cobertura_alvo"])
        )
        <= 0.5
        for registro in registros
    )
    assert all(
        float(registro["percentual_cobertura_real"]) <= 35 for registro in registros
    )
    assert all(1.3 <= float(registro["k_escala"]) <= 3.0 for registro in registros)
    assert all(float(registro["px_por_mm"]) > 0 for registro in registros)


def test_distratores_nao_alteram_a_mascara(
    sprites_catalogados: tuple[SpriteCatalogado, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Confere que os distratores visuais não entram na segmentação da placa."""
    amostra_com_distratores = generate_sample(
        sprites_catalogados,
        percentual_alvo=28,
        idade_simulada_dias=23,
        idade_maxima_dias=90,
        rng=random.Random(411),
        resolucao=(320, 240),
    )
    monkeypatch.setattr(modulo, "_desenhar_distratores", lambda *args: None)
    amostra_sem_desenho = generate_sample(
        sprites_catalogados,
        percentual_alvo=28,
        idade_simulada_dias=23,
        idade_maxima_dias=90,
        rng=random.Random(411),
        resolucao=(320, 240),
    )

    assert amostra_com_distratores.distratores_presentes
    assert (
        amostra_com_distratores.mascara.tobytes()
        == amostra_sem_desenho.mascara.tobytes()
    )


def test_mascara_coberta_e_uniao_dos_alphas_visiveis(
    sprites_catalogados: tuple[SpriteCatalogado, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Confere que os pixels positivos vêm apenas da união dos alfas opacos."""
    sprite = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    ImageDraw.Draw(sprite).ellipse((1, 1, 6, 6), fill=(32, 30, 24, 255))
    uniao_capturada: list[Image.Image] = []
    compor_original = modulo._compor_sprites

    def transformar_fixo(*args, **kwargs):
        return sprite.copy()

    def compor_capturando(*args, **kwargs):
        quantidade = compor_original(*args, **kwargs)
        uniao_capturada.append(args[1].copy())
        return quantidade

    geometria = modulo.GeometriaPlaca((320, 240), (20, 20, 300, 157), 8, 280 / 450)
    monkeypatch.setattr(modulo, "_transformar_sprite", transformar_fixo)
    monkeypatch.setattr(modulo, "_compor_sprites", compor_capturando)
    monkeypatch.setattr(
        modulo, "create_plate_geometry", lambda *args, **kwargs: geometria
    )
    monkeypatch.setattr(
        modulo,
        "_finalizar_cena",
        lambda cena, mascara, rng, rng_geometria=None: (cena.convert("RGB"), mascara),
    )

    amostra = generate_sample(
        sprites_catalogados,
        percentual_alvo=2.0,
        idade_simulada_dias=10,
        idade_maxima_dias=90,
        rng=random.Random(812),
        resolucao=(320, 240),
    )

    mascaras_esperadas = uniao_capturada[0].point(lambda valor: 2 if valor > 127 else 1)
    mascara_placa = amostra.mascara.crop(geometria.caixa)
    assert mascara_placa.tobytes() == mascaras_esperadas.tobytes()


def test_sombra_de_contato_fica_fora_da_mascara(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A sombra altera a imagem ao redor sem mudar a máscara do inseto."""
    cena = Image.new("RGBA", (32, 32), (230, 210, 150, 255))
    sprite = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    ImageDraw.Draw(sprite).ellipse((2, 2, 5, 5), fill=(30, 20, 10, 255))
    mascara = modulo._mascara_sprite(sprite)

    modulo._compor_sombra_contato(cena, sprite, (10, 10), random.Random(14))

    bbox = (10, 10, 18, 18)
    sombra = cena.crop(bbox)
    mudou_fora = False
    for y in range(8):
        for x in range(8):
            if mascara.getpixel((x, y)) == 0 and sombra.getpixel((x, y)) != (
                230,
                210,
                150,
                255,
            ):
                mudou_fora = True
    assert mudou_fora


def test_geometria_fixa_repete_a_silhueta_da_placa_entre_cenas(
    sprites_catalogados: tuple[SpriteCatalogado, ...],
) -> None:
    """Com geometria fixa a placa fica no mesmo lugar; sem ela, a captura varia."""
    resolucao = (320, 240)
    geometria = create_plate_geometry(resolucao, random.Random(7))

    def gerar(semente: int, rng_geometria: random.Random | None):
        return generate_sample(
            sprites_catalogados,
            percentual_alvo=12,
            idade_simulada_dias=10,
            idade_maxima_dias=90,
            rng=random.Random(semente),
            resolucao=resolucao,
            geometria_placa=geometria,
            rng_base=random.Random(99),
            rng_geometria=rng_geometria,
        )

    def silhueta(amostra) -> tuple[int, int, int, int] | None:
        return amostra.mascara.point(lambda valor: 255 if valor > 0 else 0).getbbox()

    fixas = [gerar(semente, random.Random(5)) for semente in range(1, 7)]
    livres = [gerar(semente, None) for semente in range(1, 7)]

    assert len({silhueta(amostra) for amostra in fixas}) == 1
    assert len({silhueta(amostra) for amostra in livres}) > 1
    assert len({amostra.imagem.tobytes() for amostra in fixas}) == len(fixas)
