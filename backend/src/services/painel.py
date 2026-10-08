"""Monta os valores derivados exibidos no painel de armadilhas."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Protocol

from src.entities import Refil, StatusAnalise
from src.services.saturacao import (
    PontoMedicao,
    calcular_dias_ate_saturar,
    calcular_em_alerta_desde,
)


class PontoPainel(Protocol):
    """Campos de uma projeção de análise necessários para o resumo do painel."""

    analisado_em: datetime
    percentual_coberto: Decimal
    status: StatusAnalise | str


@dataclass(frozen=True, slots=True)
class ResumoPainel:
    """Estado de saturação derivado de um refil e de suas leituras persistidas."""

    percentual_atual: Decimal | None
    status: StatusAnalise | None
    ultima_analise_em: datetime | None
    dias_ate_saturar: int | None
    em_alerta_desde: datetime | None


def montar_resumo(
    refil_ativo: Refil | None,
    pontos: Sequence[PontoPainel],
    data_instalacao_refil: date | None,
    limiar_trocar: Decimal,
    agora: datetime,
) -> ResumoPainel:
    """Deriva estado, projeção e alerta sem consultar banco ou serviços HTTP.

    Args:
        refil_ativo: ciclo atual da armadilha, se houver.
        pontos: leituras projetadas do refil ativo em ordem cronológica.
        data_instalacao_refil: data usada como origem da regressão.
        limiar_trocar: percentual configurado para prever a troca.
        agora: instante UTC de referência para a projeção.

    Returns:
        Resumo com a última medição persistida e os valores derivados.

    Raises:
        ValueError: se faltar a data do refil ativo ou algum instante não tiver fuso.
    """
    if refil_ativo is None or not pontos:
        return ResumoPainel(None, None, None, None, None)
    if data_instalacao_refil is None:
        raise ValueError("A data de instalação do refil ativo é obrigatória.")

    ordenados = sorted(
        pontos,
        key=lambda ponto: ponto.analisado_em.astimezone(timezone.utc),
    )
    ultima_analise = ordenados[-1]
    medicoes = [
        PontoMedicao(ponto.analisado_em, ponto.percentual_coberto)
        for ponto in ordenados
    ]
    return ResumoPainel(
        percentual_atual=ultima_analise.percentual_coberto,
        status=StatusAnalise(ultima_analise.status),
        ultima_analise_em=ultima_analise.analisado_em,
        dias_ate_saturar=calcular_dias_ate_saturar(
            medicoes,
            data_instalacao_refil,
            agora,
            limiar_trocar,
        ),
        em_alerta_desde=calcular_em_alerta_desde(medicoes, limiar_trocar),
    )


def calcular_dias_em_uso(data_instalacao: date, agora: datetime) -> int:
    """Calcula dias inteiros desde a instalação até a data UTC de referência.

    Args:
        data_instalacao: data de início do ciclo ativo.
        agora: instante de referência com fuso horário.

    Returns:
        Diferença inteira entre a data de referência UTC e a instalação.

    Raises:
        ValueError: se o instante de referência não tiver fuso horário.
    """
    if agora.tzinfo is None or agora.utcoffset() is None:
        raise ValueError("O instante atual deve incluir fuso horário.")
    return (agora.astimezone(timezone.utc).date() - data_instalacao).days


def calcular_dias_ate_troca(data_instalacao: date, data_troca: date) -> int:
    """Calcula a duração inteira do ciclo encerrado entre as duas datas.

    Args:
        data_instalacao: data em que o refil entrou em uso.
        data_troca: data em que o refil foi encerrado.

    Returns:
        Quantidade inteira de dias entre instalação e troca.
    """
    return (data_troca - data_instalacao).days
