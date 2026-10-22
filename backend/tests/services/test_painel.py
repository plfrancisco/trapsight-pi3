"""Testes puros dos valores derivados exibidos no painel."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from src.entities import StatusAnalise
from src.services.painel import montar_resumo

_AGORA = datetime(2026, 1, 11, tzinfo=timezone.utc)


def _ponto(dia: int, percentual: str, status: StatusAnalise) -> SimpleNamespace:
    """Cria uma projeção simples sem sessão ou conexão com banco."""
    return SimpleNamespace(
        analisado_em=_AGORA - timedelta(days=10 - dia),
        percentual_coberto=Decimal(percentual),
        status=status,
    )


def test_montar_resumo_sem_refil_ativo_devolve_campos_nulos() -> None:
    resumo = montar_resumo(None, [], Decimal("70"), _AGORA)

    assert resumo.percentual_atual is None
    assert resumo.status is None
    assert resumo.ultima_analise_em is None
    assert resumo.dias_ate_saturar is None
    assert resumo.em_alerta_desde is None


def test_montar_resumo_sem_analises_devolve_campos_derivados_nulos() -> None:
    resumo = montar_resumo(
        date(2026, 1, 1),
        [],
        Decimal("70"),
        _AGORA,
    )

    assert resumo.percentual_atual is None
    assert resumo.status is None
    assert resumo.ultima_analise_em is None
    assert resumo.dias_ate_saturar is None
    assert resumo.em_alerta_desde is None


def test_montar_resumo_preserva_ultima_medicao_e_status_persistido() -> None:
    pontos = [
        _ponto(10, "60.00", StatusAnalise.ATENCAO),
        _ponto(0, "20.00", StatusAnalise.OK),
    ]

    resumo = montar_resumo(
        date(2026, 1, 1),
        pontos,
        Decimal("70"),
        _AGORA,
    )

    assert resumo.percentual_atual == Decimal("60.00")
    assert resumo.status is StatusAnalise.ATENCAO
    assert resumo.ultima_analise_em == _AGORA
    assert resumo.dias_ate_saturar == 2
    assert resumo.em_alerta_desde is None


def test_montar_resumo_retorna_primeiro_cruzamento_enquanto_alerta_esta_ativo() -> None:
    pontos = [
        _ponto(0, "40.00", StatusAnalise.OK),
        _ponto(5, "72.00", StatusAnalise.TROCAR),
        _ponto(10, "81.00", StatusAnalise.TROCAR),
    ]

    resumo = montar_resumo(
        date(2026, 1, 1),
        pontos,
        Decimal("70"),
        _AGORA,
    )

    assert resumo.em_alerta_desde == _AGORA - timedelta(days=5)
