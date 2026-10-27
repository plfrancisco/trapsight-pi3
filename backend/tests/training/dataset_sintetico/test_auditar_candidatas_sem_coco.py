import pytest

from training.auditar_candidatas_sem_coco import (
    intervalo_wilson,
    selecionar_amostra,
)


def test_intervalo_wilson_retorna_limites_validos():
    inferior, superior = intervalo_wilson(75, 100)

    assert 0 < inferior < 0.75 < superior < 1


def test_intervalo_wilson_exige_contagens_validas():
    with pytest.raises(ValueError):
        intervalo_wilson(2, 1)


def test_amostra_aleatoria_e_deterministica_e_sem_reposicao():
    candidatas = [{"placa": "b", "id": indice} for indice in range(20)] + [
        {"placa": "a", "id": indice} for indice in range(20)
    ]

    primeira = selecionar_amostra(candidatas, 30, 20261021)
    segunda = selecionar_amostra(candidatas, 30, 20261021)

    assert primeira == segunda
    assert len({(item["placa"], item["id"]) for item in primeira}) == 30


def test_amostra_nao_excede_pool():
    with pytest.raises(ValueError):
        selecionar_amostra([{"placa": "a", "id": 1}], 2, 4)
