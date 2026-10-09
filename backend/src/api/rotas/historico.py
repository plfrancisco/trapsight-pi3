"""Endpoint para consultar análises de uma armadilha ao longo dos refis."""

from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.dependencias import get_session
from src.api.erros import CodigoErro, ErroDeApi, respostas_de_erro
from src.api.rotas.analises import _montar_saida
from src.api.schemas.analise import AnaliseSaida
from src.repositories.analise_repository import AnaliseRepository
from src.repositories.armadilha_repository import ArmadilhaRepository
from src.repositories.refil_repository import RefilRepository

router = APIRouter(prefix="/armadilhas", tags=["Histórico"])


class EscopoHistorico(StrEnum):
    """Escopos temporais aceitos para as análises de uma armadilha."""

    REFIL_ATIVO = "refil_ativo"
    COMPLETO = "completo"


@router.get(
    "/{armadilha_id}/analises",
    response_model=list[AnaliseSaida],
    responses=respostas_de_erro(
        CodigoErro.ARMADILHA_NAO_ENCONTRADA,
        CodigoErro.VALIDACAO_FALHOU,
        CodigoErro.ERRO_INTERNO,
    ),
)
def listar_analises_historico(
    armadilha_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    escopo: Annotated[
        EscopoHistorico,
        Query(description="Parte do histórico incluída na resposta."),
    ] = EscopoHistorico.REFIL_ATIVO,
    refil_id: Annotated[UUID | None, Query()] = None,
    limite: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> list[AnaliseSaida]:
    """Lista as análises mais recentes selecionadas em ordem cronológica.

    Args:
        armadilha_id: UUID da armadilha dona do histórico.
        session: sessão usada pelas consultas dos repositórios.
        escopo: ciclo ativo ou histórico completo, ignorado se houver refil_id.
        refil_id: ciclo específico, que precisa pertencer à armadilha da rota.
        limite: máximo entre uma e mil análises mais recentes.

    Returns:
        Lista cronológica crescente no formato público de análise.

    Raises:
        ErroDeApi: se a armadilha não existir ou o refil não pertencer a ela.
    """
    armadilha = ArmadilhaRepository(session).get_by_id(armadilha_id)
    if armadilha is None:
        raise ErroDeApi(
            CodigoErro.ARMADILHA_NAO_ENCONTRADA,
            "A armadilha solicitada não foi encontrada.",
            detalhes={"armadilha_id": str(armadilha_id)},
        )

    repositorio_analise = AnaliseRepository(session)
    if refil_id is not None:
        refil = RefilRepository(session).get_by_id(refil_id)
        if refil is None or refil.armadilha_id != armadilha_id:
            raise ErroDeApi(
                CodigoErro.VALIDACAO_FALHOU,
                "O refil informado não pertence à armadilha solicitada.",
                detalhes={"campo": "refil_id"},
            )
        analises = repositorio_analise.list_by_refil(refil_id, limit=limite)
    elif escopo is EscopoHistorico.REFIL_ATIVO:
        refil_ativo = RefilRepository(session).get_active_for_armadilha(armadilha_id)
        analises = (
            []
            if refil_ativo is None
            else repositorio_analise.list_by_refil(refil_ativo.id, limit=limite)
        )
    else:
        analises = repositorio_analise.list_by_armadilha(
            armadilha_id,
            limit=limite,
        )

    return [_montar_saida(analise, armadilha_id) for analise in analises]
