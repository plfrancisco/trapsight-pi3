"""Confere os seis estados e o histórico temporal do seed."""

from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.entities import Analise, Armadilha, Refil
from src.entities.status import StatusAnalise
from src.services.saturacao import (
    PontoMedicao,
    calcular_dias_ate_saturar,
    calcular_em_alerta_desde,
)


def _armadilha(session: Session, identificador: str) -> Armadilha:
    return session.scalars(
        select(Armadilha).where(Armadilha.identificador == identificador)
    ).one()


def test_contagens_e_estados_por_cenario(
    session: Session,
    executar_seed,
    data_seed,
    modelo_stickfly,
) -> None:
    """Cria seis armadilhas com a quantidade de ciclos e leituras esperada."""
    resultado = executar_seed(session)
    resultado.confirmar_arquivos()

    esperado = {
        "ARM-001": (1, 11),
        "ARM-002": (1, 7),
        "ARM-003": (1, 2),
        "ARM-004": (3, 12),
        "ARM-005": (1, 0),
        "ARM-006": (1, 0),
    }
    assert resultado.quantidade_armadilhas == 6
    assert resultado.quantidade_refis == 8
    assert resultado.quantidade_analises == 32
    for identificador, (quantidade_refis, quantidade_analises) in esperado.items():
        armadilha = _armadilha(session, identificador)
        assert armadilha.modelo_id == modelo_stickfly.id
        refis = list(
            session.scalars(select(Refil).where(Refil.armadilha_id == armadilha.id))
        )
        assert len(refis) == quantidade_refis
        total_analises = sum(
            len(
                list(
                    session.scalars(select(Analise).where(Analise.refil_id == refil.id))
                )
            )
            for refil in refis
        )
        assert total_analises == quantidade_analises

    idades_ativas = {
        "ARM-001": 32,
        "ARM-002": 20,
        "ARM-003": 6,
        "ARM-004": 15,
        "ARM-005": 7,
    }
    for identificador, idade in idades_ativas.items():
        armadilha = _armadilha(session, identificador)
        ativo = session.scalars(
            select(Refil).where(
                Refil.armadilha_id == armadilha.id,
                Refil.data_troca.is_(None),
            )
        ).one()
        assert ativo.data_instalacao == data_seed - timedelta(days=idade)
    armadilha_sem_refil = _armadilha(session, "ARM-006")
    assert not list(
        session.scalars(
            select(Refil).where(
                Refil.armadilha_id == armadilha_sem_refil.id,
                Refil.data_troca.is_(None),
            )
        )
    )

    for identificador, status_esperado in (
        ("ARM-001", StatusAnalise.TROCAR),
        ("ARM-002", StatusAnalise.ATENCAO),
        ("ARM-003", StatusAnalise.OK),
    ):
        armadilha = _armadilha(session, identificador)
        ultima = session.scalars(
            select(Analise)
            .join(Refil, Analise.refil_id == Refil.id)
            .where(Refil.armadilha_id == armadilha.id)
            .order_by(Analise.analisado_em.desc())
        ).first()
        assert ultima is not None
        assert StatusAnalise(ultima.status) is status_esperado

    refis_004 = list(
        session.scalars(
            select(Refil)
            .where(Refil.armadilha_id == _armadilha(session, "ARM-004").id)
            .order_by(Refil.data_instalacao)
        )
    )
    assert [
        (refil.data_troca - refil.data_instalacao).days
        for refil in refis_004
        if refil.data_troca is not None
    ] == [38, 45]
    assert refis_004[-1].data_instalacao == data_seed - timedelta(days=15)
    assert refis_004[-1].data_troca is None
    assert _armadilha(session, "ARM-006").data_instalacao == data_seed - timedelta(
        days=38
    )


def test_datas_sao_relativas_ao_relogio_mockado(
    session: Session,
    executar_seed,
    data_seed,
) -> None:
    """Alinha instalação, troca e medições ao dia fornecido pelo relógio."""
    resultado = executar_seed(session)
    resultado.confirmar_arquivos()

    armadilha = _armadilha(session, "ARM-001")
    refil = session.scalars(
        select(Refil).where(Refil.armadilha_id == armadilha.id)
    ).one()
    analises = list(
        session.scalars(
            select(Analise)
            .where(Analise.refil_id == refil.id)
            .order_by(Analise.analisado_em)
        )
    )
    assert refil.data_instalacao == data_seed - timedelta(days=32)
    assert [item.analisado_em.date() for item in analises] == [
        data_seed - timedelta(days=30 - 3 * indice) for indice in range(11)
    ]
    assert analises[-2].analisado_em.date() == data_seed - timedelta(days=3)
    assert analises[-1].analisado_em.date() == data_seed
    pontos = [
        PontoMedicao(item.analisado_em, item.percentual_coberto) for item in analises
    ]
    alerta_desde = calcular_em_alerta_desde(pontos, Decimal("70"))
    assert alerta_desde is not None
    assert alerta_desde.date() == data_seed - timedelta(days=3)


def test_projecao_armadilha_002_fica_em_torno_de_cinco_dias(
    session: Session,
    executar_seed,
    data_seed,
) -> None:
    """A regressão de produção projeta a saturação a partir das sete leituras."""
    resultado = executar_seed(session)
    resultado.confirmar_arquivos()

    armadilha = _armadilha(session, "ARM-002")
    refil = session.scalars(
        select(Refil).where(
            Refil.armadilha_id == armadilha.id,
            Refil.data_troca.is_(None),
        )
    ).one()
    analises = list(
        session.scalars(
            select(Analise)
            .where(Analise.refil_id == refil.id)
            .order_by(Analise.analisado_em)
        )
    )
    pontos = [
        PontoMedicao(item.analisado_em, item.percentual_coberto) for item in analises
    ]
    agora = datetime.combine(data_seed, time(12), timezone.utc)
    dias = calcular_dias_ate_saturar(
        pontos,
        refil.data_instalacao,
        agora,
        Decimal("70"),
    )
    assert dias is not None
    assert 4 <= dias <= 6
