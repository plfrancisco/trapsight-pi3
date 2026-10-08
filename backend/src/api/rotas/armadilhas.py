"""Endpoints de cadastro, listagem e detalhe das armadilhas."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.api.dependencias import get_agora, get_session, get_settings
from src.api.erros import CodigoErro, ErroDeApi, respostas_de_erro
from src.api.schemas.armadilha import (
    ArmadilhaAtualizar,
    ArmadilhaCriar,
    ArmadilhaDetalhe,
    ArmadilhaLista,
    RefilAnteriorSaida,
    RefilAtivoSaida,
)
from src.config.settings import Settings
from src.entities import Armadilha, Refil, StatusAnalise
from src.repositories.analise_repository import AnaliseRepository, PontoAnalise
from src.repositories.armadilha_repository import ArmadilhaRepository
from src.repositories.exceptions import IdentificadorDuplicado
from src.repositories.refil_repository import RefilRepository
from src.services.painel import (
    calcular_dias_ate_troca,
    calcular_dias_em_uso,
    montar_resumo,
)

router = APIRouter(prefix="/armadilhas", tags=["Armadilhas"])


@router.get(
    "",
    response_model=list[ArmadilhaLista],
    responses=respostas_de_erro(CodigoErro.ERRO_INTERNO),
)
def listar_armadilhas(
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    agora: Annotated[datetime, Depends(get_agora)],
) -> list[ArmadilhaLista]:
    """Lista o estado consolidado das armadilhas usando três consultas.

    Args:
        session: sessão da requisição.
        settings: limiar de troca validado no início da aplicação.
        agora: instante UTC fornecido pela dependência da aplicação.

    Returns:
        Itens do painel ordenados pelo estado e previsão de saturação.
    """
    armadilhas = ArmadilhaRepository(session).list_all()
    refis_ativos = RefilRepository(session).list_active()
    pontos_por_refil = AnaliseRepository(session).list_pontos_by_refil_ids(
        [refil.id for refil in refis_ativos]
    )
    refil_por_armadilha = {refil.armadilha_id: refil for refil in refis_ativos}
    itens = [
        _montar_item_lista(
            armadilha,
            refil_por_armadilha.get(armadilha.id),
            pontos_por_refil,
            Decimal(settings.limiar_trocar),
            agora,
        )
        for armadilha in armadilhas
    ]
    return sorted(
        itens,
        key=lambda item: (
            item.status is not StatusAnalise.TROCAR,
            item.dias_ate_saturar is None,
            item.dias_ate_saturar if item.dias_ate_saturar is not None else 0,
            item.identificador,
        ),
    )


@router.post(
    "",
    response_model=ArmadilhaDetalhe,
    status_code=status.HTTP_201_CREATED,
    responses=respostas_de_erro(
        CodigoErro.IDENTIFICADOR_DUPLICADO,
        CodigoErro.VALIDACAO_FALHOU,
        CodigoErro.ERRO_INTERNO,
    ),
)
def criar_armadilha(
    dados: ArmadilhaCriar,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    agora: Annotated[datetime, Depends(get_agora)],
) -> ArmadilhaDetalhe:
    """Cria uma armadilha e, se pedido, seu primeiro refil na mesma transação.

    Args:
        dados: campos validados do cadastro.
        session: sessão que mantém as gravações na mesma transação.
        settings: configuração usada para montar o estado inicial.
        agora: instante UTC usado no resumo de uso.

    Returns:
        Detalhe da armadilha criada.
    """
    try:
        armadilha = ArmadilhaRepository(session).create(
            identificador=dados.identificador,
            modelo=dados.modelo,
            localizacao=dados.localizacao,
            data_instalacao=dados.data_instalacao,
        )
    except IdentificadorDuplicado:
        raise _erro_identificador_duplicado(dados.identificador) from None

    refil_ativo = None
    if dados.criar_refil_inicial:
        assert dados.data_instalacao is not None
        refil_ativo = RefilRepository(session).create(
            armadilha_id=armadilha.id,
            data_instalacao=dados.data_instalacao,
        )

    resposta = _montar_detalhe(
        armadilha,
        refil_ativo,
        [],
        [],
        Decimal(settings.limiar_trocar),
        agora,
    )
    session.commit()
    return resposta


@router.get(
    "/{armadilha_id}",
    response_model=ArmadilhaDetalhe,
    responses=respostas_de_erro(
        CodigoErro.ARMADILHA_NAO_ENCONTRADA,
        CodigoErro.VALIDACAO_FALHOU,
        CodigoErro.ERRO_INTERNO,
    ),
)
def obter_armadilha(
    armadilha_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    agora: Annotated[datetime, Depends(get_agora)],
) -> ArmadilhaDetalhe:
    """Devolve o detalhe e o histórico de ciclos de uma armadilha.

    Args:
        armadilha_id: UUID da armadilha solicitada.
        session: sessão da requisição.
        settings: limiar usado para derivar a projeção atual.
        agora: instante UTC usado no resumo de uso.

    Returns:
        Detalhe com refil atual, ciclos encerrados e última leitura.

    Raises:
        ErroDeApi: se a armadilha não existir.
    """
    repositorio_armadilha = ArmadilhaRepository(session)
    armadilha = repositorio_armadilha.get_by_id(armadilha_id)
    if armadilha is None:
        raise _erro_armadilha_nao_encontrada(armadilha_id)

    repositorio_refil = RefilRepository(session)
    refil_ativo = repositorio_refil.get_active_for_armadilha(armadilha_id)
    refis_anteriores = repositorio_refil.list_closed_for_armadilha(armadilha_id)
    pontos_por_refil = AnaliseRepository(session).list_pontos_by_refil_ids(
        [] if refil_ativo is None else [refil_ativo.id]
    )
    pontos = [] if refil_ativo is None else pontos_por_refil[refil_ativo.id]
    return _montar_detalhe(
        armadilha,
        refil_ativo,
        refis_anteriores,
        pontos,
        Decimal(settings.limiar_trocar),
        agora,
    )


@router.patch(
    "/{armadilha_id}",
    response_model=ArmadilhaDetalhe,
    responses=respostas_de_erro(
        CodigoErro.ARMADILHA_NAO_ENCONTRADA,
        CodigoErro.IDENTIFICADOR_DUPLICADO,
        CodigoErro.VALIDACAO_FALHOU,
        CodigoErro.ERRO_INTERNO,
    ),
)
def atualizar_armadilha(
    armadilha_id: UUID,
    dados: ArmadilhaAtualizar,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    agora: Annotated[datetime, Depends(get_agora)],
) -> ArmadilhaDetalhe:
    """Atualiza apenas os campos presentes no corpo da requisição.

    Args:
        armadilha_id: UUID da armadilha a atualizar.
        dados: campos editáveis informados pelo cliente.
        session: sessão da requisição.
        settings: limiar usado para derivar a projeção atual.
        agora: instante UTC usado no resumo de uso.

    Returns:
        Detalhe da armadilha depois da atualização.

    Raises:
        ErroDeApi: se a armadilha não existir ou o identificador estiver ocupado.
    """
    campos = {nome: getattr(dados, nome) for nome in dados.model_fields_set}
    try:
        armadilha = ArmadilhaRepository(session).update(armadilha_id, **campos)
    except IdentificadorDuplicado:
        identificador = campos.get("identificador")
        if not isinstance(identificador, str):
            raise
        raise _erro_identificador_duplicado(identificador) from None
    if armadilha is None:
        raise _erro_armadilha_nao_encontrada(armadilha_id)

    repositorio_refil = RefilRepository(session)
    refil_ativo = repositorio_refil.get_active_for_armadilha(armadilha_id)
    refis_anteriores = repositorio_refil.list_closed_for_armadilha(armadilha_id)
    pontos_por_refil = AnaliseRepository(session).list_pontos_by_refil_ids(
        [] if refil_ativo is None else [refil_ativo.id]
    )
    pontos = [] if refil_ativo is None else pontos_por_refil[refil_ativo.id]
    resposta = _montar_detalhe(
        armadilha,
        refil_ativo,
        refis_anteriores,
        pontos,
        Decimal(settings.limiar_trocar),
        agora,
    )
    session.commit()
    return resposta


def _montar_item_lista(
    armadilha: Armadilha,
    refil_ativo: Refil | None,
    pontos_por_refil: dict[UUID, list[PontoAnalise]],
    limiar_trocar: Decimal,
    agora: datetime,
) -> ArmadilhaLista:
    """Monta uma linha da listagem a partir das leituras já carregadas."""
    pontos = [] if refil_ativo is None else pontos_por_refil[refil_ativo.id]
    resumo = montar_resumo(
        refil_ativo,
        pontos,
        None if refil_ativo is None else refil_ativo.data_instalacao,
        limiar_trocar,
        agora,
    )
    return ArmadilhaLista(
        id=armadilha.id,
        identificador=armadilha.identificador,
        localizacao=armadilha.localizacao,
        modelo=armadilha.modelo,
        refil_ativo=_montar_refil_ativo(refil_ativo, agora),
        percentual_atual=resumo.percentual_atual,
        status=resumo.status,
        dias_ate_saturar=resumo.dias_ate_saturar,
        ultima_analise_em=resumo.ultima_analise_em,
        em_alerta_desde=resumo.em_alerta_desde,
    )


def _montar_detalhe(
    armadilha: Armadilha,
    refil_ativo: Refil | None,
    refis_anteriores: list[Refil],
    pontos: list[PontoAnalise],
    limiar_trocar: Decimal,
    agora: datetime,
) -> ArmadilhaDetalhe:
    """Monta o corpo detalhado sem buscar relações implicitamente."""
    resumo = montar_resumo(
        refil_ativo,
        pontos,
        None if refil_ativo is None else refil_ativo.data_instalacao,
        limiar_trocar,
        agora,
    )
    return ArmadilhaDetalhe(
        id=armadilha.id,
        identificador=armadilha.identificador,
        modelo=armadilha.modelo,
        localizacao=armadilha.localizacao,
        data_instalacao=armadilha.data_instalacao,
        refil_ativo=_montar_refil_ativo(refil_ativo, agora),
        refis_anteriores=[
            RefilAnteriorSaida(
                id=refil.id,
                data_instalacao=refil.data_instalacao,
                data_troca=refil.data_troca,
                dias_ate_troca=calcular_dias_ate_troca(
                    refil.data_instalacao,
                    refil.data_troca,
                ),
            )
            for refil in refis_anteriores
            if refil.data_troca is not None
        ],
        percentual_atual=resumo.percentual_atual,
        status=resumo.status,
        dias_ate_saturar=resumo.dias_ate_saturar,
    )


def _montar_refil_ativo(
    refil: Refil | None,
    agora: datetime,
) -> RefilAtivoSaida | None:
    """Monta o ciclo atual e calcula seus dias inteiros em uso."""
    if refil is None:
        return None
    dias_em_uso = calcular_dias_em_uso(refil.data_instalacao, agora)
    return RefilAtivoSaida(
        id=refil.id,
        data_instalacao=refil.data_instalacao,
        dias_em_uso=dias_em_uso,
    )


def _erro_armadilha_nao_encontrada(armadilha_id: UUID) -> ErroDeApi:
    """Cria o erro de domínio público associado a um UUID inexistente."""
    return ErroDeApi(
        CodigoErro.ARMADILHA_NAO_ENCONTRADA,
        "A armadilha solicitada não foi encontrada.",
        detalhes={"armadilha_id": str(armadilha_id)},
    )


def _erro_identificador_duplicado(identificador: str) -> ErroDeApi:
    """Cria o erro público de conflito para um identificador já cadastrado."""
    return ErroDeApi(
        CodigoErro.IDENTIFICADOR_DUPLICADO,
        "Já existe uma armadilha com este identificador.",
        detalhes={"identificador": identificador},
    )
