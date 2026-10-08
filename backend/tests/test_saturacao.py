"""Testa os cálculos puros de projeção de saturação e início de alerta."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from math import floor

import pytest

from src.services.saturacao import (
    PontoMedicao,
    calcular_dias_ate_saturar,
    calcular_em_alerta_desde,
)

LIMIAR = Decimal("70")
DATA_INSTALACAO = date(2026, 1, 1)
INICIO = datetime(2026, 1, 1, tzinfo=timezone.utc)


def ponto(dia: int, percentual: str) -> PontoMedicao:
    """Cria uma medição de teste no dia informado após a instalação."""
    return PontoMedicao(INICIO + timedelta(days=dia), Decimal(percentual))


def test_ponto_medicao_e_imutavel_e_usa_decimal() -> None:
    medicao = ponto(0, "12.34")

    assert medicao.percentual == Decimal("12.34")
    with pytest.raises((AttributeError, TypeError)):
        medicao.percentual = Decimal("20")  # type: ignore[misc]


def test_ponto_medicao_rejeita_percentual_fora_da_faixa() -> None:
    with pytest.raises(ValueError):
        PontoMedicao(INICIO, Decimal("100.01"))


def test_ponto_medicao_rejeita_datetime_sem_fuso() -> None:
    with pytest.raises(ValueError, match="fuso horário"):
        PontoMedicao(datetime(2026, 1, 1), Decimal("10"))


def test_calculo_linear_exato() -> None:
    pontos = [ponto(0, "10"), ponto(5, "40")]

    resultado = calcular_dias_ate_saturar(
        pontos, DATA_INSTALACAO, INICIO + timedelta(days=5), LIMIAR
    )

    assert resultado == 5


@pytest.mark.parametrize(
    ("pontos", "dia_atual", "esperado"),
    [
        ([], 10, None),
        ([ponto(0, "10")], 10, None),
        ([ponto(0, "40"), ponto(5, "30")], 10, None),
        ([ponto(0, "10"), ponto(1, "80")], 1, 0),
        ([ponto(0, "50"), ponto(1, "80"), ponto(2, "60")], 5, 0),
    ],
    ids=[
        "sem-pontos",
        "menos-de-duas",
        "inclinacao-nao-positiva",
        "limiar-ja-ultrapassado",
        "previsao-passada",
    ],
)
def test_condicoes_sem_estimativa_ou_com_zero(
    pontos: list[PontoMedicao], dia_atual: int, esperado: int | None
) -> None:
    resultado = calcular_dias_ate_saturar(
        pontos, DATA_INSTALACAO, INICIO + timedelta(days=dia_atual), LIMIAR
    )

    assert resultado == esperado


def test_regressao_considera_todos_os_pontos() -> None:
    pontos = [
        ponto(0, "10"),
        ponto(1, "16"),
        ponto(2, "22"),
        ponto(3, "28"),
        ponto(4, "34"),
        ponto(5, "40"),
        ponto(6, "46"),
        ponto(7, "52"),
        ponto(8, "58"),
        ponto(9, "58"),
    ]

    resultado = calcular_dias_ate_saturar(
        pontos, DATA_INSTALACAO, INICIO + timedelta(days=9), LIMIAR
    )

    assert resultado == 1
    projecao_pelos_extremos = (LIMIAR - Decimal("10")) / (
        Decimal("58") - Decimal("10")
    ) * 9 - 9
    assert floor(projecao_pelos_extremos) == 2


def test_arredonda_para_baixo_e_nao_devolve_valor_negativo() -> None:
    pontos = [ponto(0, "10"), ponto(1, "30")]

    previsto = calcular_dias_ate_saturar(pontos, DATA_INSTALACAO, INICIO, Decimal("65"))
    vencido = calcular_dias_ate_saturar(
        pontos, DATA_INSTALACAO, INICIO + timedelta(days=5), Decimal("65")
    )

    assert previsto == 2
    assert vencido == 0


def test_calculo_independe_da_ordem_de_entrada() -> None:
    pontos = [ponto(5, "40"), ponto(0, "10"), ponto(2, "22")]

    resultado = calcular_dias_ate_saturar(
        pontos, DATA_INSTALACAO, INICIO + timedelta(days=5), LIMIAR
    )

    assert resultado == 5


def test_calculo_retorna_none_quando_x_tem_variancia_nula() -> None:
    mesmo_instante = [ponto(2, "40"), ponto(2, "50"), ponto(2, "60")]

    resultado = calcular_dias_ate_saturar(
        mesmo_instante, DATA_INSTALACAO, INICIO + timedelta(days=3), LIMIAR
    )

    assert resultado is None


def test_calculo_rejeita_agora_sem_fuso() -> None:
    with pytest.raises(ValueError, match="fuso horário"):
        calcular_dias_ate_saturar(
            [ponto(0, "10"), ponto(1, "20")],
            DATA_INSTALACAO,
            datetime(2026, 1, 2),
            LIMIAR,
        )


@pytest.mark.parametrize(
    ("pontos", "esperado"),
    [
        ([ponto(0, "60"), ponto(2, "71"), ponto(3, "80")], INICIO + timedelta(days=2)),
        ([ponto(0, "60"), ponto(2, "71"), ponto(3, "60")], None),
        (
            [ponto(0, "60"), ponto(2, "71"), ponto(3, "60"), ponto(4, "80")],
            INICIO + timedelta(days=2),
        ),
        ([ponto(0, "60"), ponto(1, "70")], None),
        ([], None),
    ],
    ids=[
        "cruzou-e-continua",
        "cruzou-e-voltou",
        "cruzou-caiu-cruzou",
        "igual-limiar",
        "sem-pontos",
    ],
)
def test_inicio_do_alerta(
    pontos: list[PontoMedicao], esperado: datetime | None
) -> None:
    resultado = calcular_em_alerta_desde(pontos, LIMIAR)

    assert resultado == esperado


def test_inicio_do_alerta_independe_da_ordem_de_entrada() -> None:
    pontos = [ponto(4, "80"), ponto(2, "71"), ponto(0, "60")]

    resultado = calcular_em_alerta_desde(pontos, LIMIAR)

    assert resultado == INICIO + timedelta(days=2)
