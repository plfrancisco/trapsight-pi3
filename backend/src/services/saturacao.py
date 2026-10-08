"""Calcula a projeção de saturação e o início de alertas a partir de medições."""

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from decimal import Decimal
from math import floor
from typing import Iterable

_MICROSSEGUNDOS_POR_DIA = Decimal(86_400_000_000)


@dataclass(frozen=True)
class PontoMedicao:
    """Representa um percentual medido em um instante com fuso horário.

    Args:
        analisado_em: Instante da análise, obrigatoriamente com fuso horário.
        percentual: Percentual medido, como Decimal entre zero e cem.

    Raises:
        ValueError: Se o instante não tiver fuso ou o percentual estiver fora
            do intervalo permitido.
        TypeError: Se o percentual não for Decimal.
    """

    analisado_em: datetime
    percentual: Decimal

    def __post_init__(self) -> None:
        if (
            not isinstance(self.analisado_em, datetime)
            or self.analisado_em.tzinfo is None
            or self.analisado_em.utcoffset() is None
        ):
            raise ValueError("O instante da medição deve incluir fuso horário.")
        if not isinstance(self.percentual, Decimal):
            raise TypeError("O percentual deve ser Decimal.")
        if not self.percentual.is_finite() or not Decimal(0) <= self.percentual <= 100:
            raise ValueError("O percentual deve estar entre zero e cem.")


def calcular_dias_ate_saturar(
    pontos: Iterable[PontoMedicao],
    data_instalacao: date,
    agora: datetime,
    limiar_trocar: Decimal,
) -> int | None:
    """Estima dias restantes até o refil atingir o limiar de troca.

    A regressão usa cada medição para reduzir o efeito do ruído de leituras
    individuais, em vez de deixar que apenas os extremos determinem a taxa.
    O arredondamento para baixo evita prometer mais tempo do que a projeção
    indica antes do próximo dia inteiro.

    Args:
        pontos: Medições associadas ao refil ativo.
        data_instalacao: Data usada como dia zero, à meia-noite UTC.
        agora: Instante de referência, obrigatoriamente com fuso horário.
        limiar_trocar: Percentual acima do qual o refil deve ser trocado.

    Returns:
        Dias inteiros não negativos até o limiar, ou None sem base para
        calcular uma tendência crescente.

    Raises:
        ValueError: Se ``agora`` não tiver fuso horário ou a instalação não
            for uma data.
        TypeError: Se o limiar não for Decimal.
    """
    _validar_data_com_fuso(agora)
    _validar_limiar(limiar_trocar)
    if isinstance(data_instalacao, datetime) or not isinstance(data_instalacao, date):
        raise ValueError("A data de instalação deve ser uma data sem horário.")

    ordenados = _ordenar_pontos(pontos)
    if len(ordenados) < 2:
        return None

    inicio = datetime.combine(data_instalacao, time.min, tzinfo=timezone.utc)
    xs = [_dias_entre(inicio, ponto.analisado_em) for ponto in ordenados]
    ys = [ponto.percentual for ponto in ordenados]
    media_x = sum(xs, Decimal(0)) / len(xs)
    media_y = sum(ys, Decimal(0)) / len(ys)
    variancia_x = sum((x - media_x) ** 2 for x in xs)
    if variancia_x == 0:
        return None

    covariancia = sum((x - media_x) * (y - media_y) for x, y in zip(xs, ys))
    inclinacao = covariancia / variancia_x
    if inclinacao <= 0:
        return None
    if ordenados[-1].percentual > limiar_trocar:
        return 0

    intercepto = media_y - inclinacao * media_x
    dias_previstos = (limiar_trocar - intercepto) / inclinacao
    dias_decorridos = _dias_entre(inicio, agora)
    return max(0, floor(dias_previstos - dias_decorridos))


def calcular_em_alerta_desde(
    pontos: Iterable[PontoMedicao], limiar_trocar: Decimal
) -> datetime | None:
    """Retorna o primeiro cruzamento do limiar se a última leitura o mantém.

    Args:
        pontos: Medições associadas ao refil ativo.
        limiar_trocar: Percentual que precisa ser ultrapassado para alertar.

    Returns:
        Instante da primeira medição acima do limiar enquanto o alerta segue
        ativo, ou None quando não há cruzamento ativo.

    Raises:
        TypeError: Se o limiar não for Decimal.
    """
    _validar_limiar(limiar_trocar)
    ordenados = _ordenar_pontos(pontos)
    if not ordenados or ordenados[-1].percentual <= limiar_trocar:
        return None

    return next(
        ponto.analisado_em for ponto in ordenados if ponto.percentual > limiar_trocar
    )


def _dias_entre(inicio: datetime, fim: datetime) -> Decimal:
    """Converte dois instantes em dias fracionários sem perda de microssegundos."""
    diferenca = fim.astimezone(timezone.utc) - inicio.astimezone(timezone.utc)
    microssegundos = (
        Decimal(diferenca.days * 86_400 + diferenca.seconds) * 1_000_000
        + diferenca.microseconds
    )
    return microssegundos / _MICROSSEGUNDOS_POR_DIA


def _ordenar_pontos(pontos: Iterable[PontoMedicao]) -> list[PontoMedicao]:
    """Ordena pelo instante UTC para respeitar mudanças de offset e horário de verão."""
    return sorted(
        pontos,
        key=lambda ponto: ponto.analisado_em.astimezone(timezone.utc),
    )


def _validar_data_com_fuso(instante: datetime) -> None:
    """Rejeita instantes sem fuso para manter as datas comparáveis em UTC."""
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise ValueError("O instante deve incluir fuso horário.")


def _validar_limiar(limiar_trocar: Decimal) -> None:
    """Garante que os cálculos mantenham a precisão decimal do domínio."""
    if not isinstance(limiar_trocar, Decimal):
        raise TypeError("O limiar deve ser Decimal.")
    if not limiar_trocar.is_finite():
        raise ValueError("O limiar deve ser um Decimal finito.")
