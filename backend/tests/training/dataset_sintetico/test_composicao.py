"""Verifica a cobertura da placa e a independência dos distratores."""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

import training.dataset_sintetico as modulo
from training.dataset_sintetico import SpriteCatalogado, generate_sample


def test_convergencia_das_tres_faixas_de_cobertura(
    tmp_path: Path,
    gerar_dataset_teste,
) -> None:
    """Gera amostras estratificadas e registra a taxa de alvo atingido."""
    registros = gerar_dataset_teste(
        tmp_path / "dataset",
        quantidade=90,
        semente=20261021,
    )
    fracoes = {
        faixa: sum(
            registro["alvo_atingido"] is True
            for registro in registros
            if registro["faixa_cobertura_alvo"] == faixa
        )
        / sum(registro["faixa_cobertura_alvo"] == faixa for registro in registros)
        for faixa in ("ok", "atencao", "trocar")
    }
    print(f"Frações de alvo atingido por faixa: {json.dumps(fracoes, sort_keys=True)}")

    assert all(fracao >= 0.8 for fracao in fracoes.values()), (
        f"Frações de alvo atingido por faixa: {fracoes}"
    )


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
