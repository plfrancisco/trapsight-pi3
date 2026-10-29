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

# O seed foi escrito para limiares de 40% e 70%. Com os limiares do produto
# (10% e 20%), cada percentual dos cenários e cada limite em pontos percentuais
# destes testes foi multiplicado por 20/70. A mesma razão vale para as taxas.
ESCALA_SEED = Decimal(2) / Decimal(7)
LIMIAR_TROCAR = Decimal("20")


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
    alerta_desde = calcular_em_alerta_desde(pontos, LIMIAR_TROCAR)
    assert alerta_desde is not None
    assert alerta_desde.date() == data_seed - timedelta(days=3)


def test_armadilha_001_suaviza_a_leitura_antes_do_alerta(
    session: Session,
    executar_seed,
) -> None:
    """Limita o crescimento entre a nona e a décima leitura."""
    resultado = executar_seed(session)
    resultado.confirmar_arquivos()

    armadilha = _armadilha(session, "ARM-001")
    leituras = list(
        session.scalars(
            select(Analise)
            .join(Refil, Analise.refil_id == Refil.id)
            .where(Refil.armadilha_id == armadilha.id)
            .order_by(Analise.analisado_em)
        )
    )

    salto = leituras[9].percentual_coberto - leituras[8].percentual_coberto
    assert Decimal("0") < salto <= Decimal("10") * ESCALA_SEED


def test_armadilha_004_cresce_na_taxa_historica_com_variacao(
    session: Session,
    executar_seed,
) -> None:
    """Mantém a curva ativa perto da taxa anterior e do alvo final definido."""
    resultado = executar_seed(session)
    resultado.confirmar_arquivos()

    armadilha = _armadilha(session, "ARM-004")
    refil_ativo = session.scalars(
        select(Refil).where(
            Refil.armadilha_id == armadilha.id,
            Refil.data_troca.is_(None),
        )
    ).one()
    leituras = list(
        session.scalars(
            select(Analise)
            .where(Analise.refil_id == refil_ativo.id)
            .order_by(Analise.analisado_em)
        )
    )

    assert len(leituras) == 5
    assert (
        Decimal("25") * ESCALA_SEED
        <= leituras[-1].percentual_coberto
        <= Decimal("30") * ESCALA_SEED
    )
    dias = (leituras[-1].analisado_em - leituras[0].analisado_em).days
    taxa_media = (
        leituras[-1].percentual_coberto - leituras[0].percentual_coberto
    ) / Decimal(dias)
    assert Decimal("1.3") * ESCALA_SEED <= taxa_media <= Decimal("1.9") * ESCALA_SEED
    taxas_por_intervalo = [
        (seguinte.percentual_coberto - anterior.percentual_coberto) / Decimal(3)
        for anterior, seguinte in zip(leituras, leituras[1:], strict=False)
    ]
    assert max(taxas_por_intervalo) - min(taxas_por_intervalo) >= (
        Decimal("0.3") * ESCALA_SEED
    )


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
        LIMIAR_TROCAR,
    )
    assert dias is not None
    assert 4 <= dias <= 6
