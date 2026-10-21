"""Verifica que os distratores visuais não entram na máscara."""

from __future__ import annotations

import random

import pytest

import training.dataset_sintetico as modulo
from training.dataset_sintetico import SpriteCatalogado, generate_sample


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
