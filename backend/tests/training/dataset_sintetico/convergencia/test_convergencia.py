"""Mede a proporção de amostras que atingem o alvo em cada faixa."""

from __future__ import annotations

import json
from pathlib import Path


def test_convergencia_das_tres_faixas_de_cobertura(
    tmp_path: Path,
    gerar_dataset_teste,
) -> None:
    """Gera amostras estratificadas e registra a taxa de alvo atingido."""
    registros = gerar_dataset_teste(
        tmp_path / "dataset",
        quantidade=90,
        semente=20261021,
        limite_sprites=600,
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
