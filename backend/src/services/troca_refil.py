"""Orquestra a troca atômica de um ciclo de refil."""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from src.repositories.armadilha_repository import ArmadilhaRepository
from src.repositories.exceptions import ErroDeDominio
from src.repositories.refil_repository import RefilRepository
from src.services.painel import calcular_dias_ate_troca, calcular_dias_em_uso


class ArmadilhaNaoEncontrada(ErroDeDominio):
    """Indica que não há armadilha correspondente ao identificador solicitado."""


class DataInstalacaoFutura(ErroDeDominio):
    """Indica que o novo ciclo não pode começar depois da data UTC atual."""


@dataclass(frozen=True, slots=True)
class RefilEncerradoCalculado:
    """Dados calculados do ciclo que foi encerrado pela troca."""

    id: UUID
    data_instalacao: date
    data_troca: date
    dias_ate_troca: int


@dataclass(frozen=True, slots=True)
class RefilNovoCalculado:
    """Dados calculados do ciclo que começa com a troca."""

    id: UUID
    data_instalacao: date
    dias_em_uso: int


@dataclass(frozen=True, slots=True)
class ResultadoTrocaRefil:
    """Resultado da troca sem dependência de formatos HTTP."""

    refil_encerrado: RefilEncerradoCalculado | None
    refil_novo: RefilNovoCalculado


def trocar_refil(
    session: Session,
    armadilha_id: UUID,
    data_instalacao: date,
    agora: datetime,
) -> ResultadoTrocaRefil:
    """Valida e persiste os dois lados da troca na transação do chamador.

    Args:
        session: sessão cuja transação será confirmada ou revertida pela rota.
        armadilha_id: UUID da armadilha que receberá o novo ciclo.
        data_instalacao: data informada para início do novo ciclo.
        agora: instante UTC usado para validar datas e calcular dias em uso.

    Returns:
        Resumos do ciclo encerrado, se houver, e do novo ciclo ativo.

    Raises:
        ArmadilhaNaoEncontrada: se a armadilha não existir.
        DataInstalacaoFutura: se a data informada estiver no futuro.
        DataTrocaInvalida: se a troca anteceder a instalação do ciclo atual.
        RefilAtivoExistente: se uma inconsistência concorrente persistir.
    """
    armadilha = ArmadilhaRepository(session).get_by_id_for_update(armadilha_id)
    if armadilha is None:
        raise ArmadilhaNaoEncontrada(armadilha_id)

    if data_instalacao > agora.astimezone(timezone.utc).date():
        raise DataInstalacaoFutura(data_instalacao)

    repositorio_refil = RefilRepository(session)
    refil_ativo = repositorio_refil.get_active_for_armadilha(armadilha_id)
    refil_encerrado = None
    if refil_ativo is not None:
        ciclo_encerrado = repositorio_refil.close(refil_ativo.id, data_instalacao)
        if ciclo_encerrado is not None:
            refil_encerrado = RefilEncerradoCalculado(
                id=ciclo_encerrado.id,
                data_instalacao=ciclo_encerrado.data_instalacao,
                data_troca=data_instalacao,
                dias_ate_troca=calcular_dias_ate_troca(
                    ciclo_encerrado.data_instalacao,
                    data_instalacao,
                ),
            )

    ciclo_novo = repositorio_refil.create(
        armadilha_id=armadilha_id,
        data_instalacao=data_instalacao,
    )
    return ResultadoTrocaRefil(
        refil_encerrado=refil_encerrado,
        refil_novo=RefilNovoCalculado(
            id=ciclo_novo.id,
            data_instalacao=ciclo_novo.data_instalacao,
            dias_em_uso=calcular_dias_em_uso(ciclo_novo.data_instalacao, agora),
        ),
    )
