"""Endpoint de consulta ao catálogo de modelos de armadilha."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.dependencias import get_session
from src.api.erros import CodigoErro, respostas_de_erro
from src.api.schemas.modelo_armadilha import ModeloArmadilhaSaida
from src.repositories.modelo_armadilha_repository import ModeloArmadilhaRepository

router = APIRouter(prefix="/modelos-armadilha", tags=["modelos"])


@router.get(
    "",
    response_model=list[ModeloArmadilhaSaida],
    responses=respostas_de_erro(CodigoErro.ERRO_INTERNO),
)
def listar_modelos(
    session: Annotated[Session, Depends(get_session)],
) -> list[ModeloArmadilhaSaida]:
    """Lista os modelos disponíveis para cadastrar uma nova armadilha.

    Args:
        session: sessão da requisição.

    Returns:
        Modelos ativos do catálogo, ordenados pelo nome.
    """
    return [
        ModeloArmadilhaSaida.model_validate(modelo)
        for modelo in ModeloArmadilhaRepository(session).list_ativos()
    ]
