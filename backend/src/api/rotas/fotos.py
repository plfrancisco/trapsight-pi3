"""Foto de identificação opcional da armadilha: envio, remoção e leitura."""

import asyncio
import hashlib
from datetime import datetime, timezone
from email.utils import format_datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.dependencias import get_session
from src.api.erros import CodigoErro, ErroDeApi, respostas_de_erro
from src.api.rotas.analises import (
    ler_upload_limitado,
    requisicao_nao_modificada,
    validar_upload_imagem,
)
from src.repositories.armadilha_repository import ArmadilhaRepository
from src.services.foto_armadilha import preparar_foto, url_da_foto

router = APIRouter(prefix="/armadilhas", tags=["Armadilhas"])


class FotoSaida(BaseModel):
    """Estado da foto de identificação depois de um envio."""

    foto_tipo: str
    foto_url: str


def _erro_armadilha(armadilha_id: UUID) -> ErroDeApi:
    return ErroDeApi(
        CodigoErro.ARMADILHA_NAO_ENCONTRADA,
        "A armadilha solicitada não foi encontrada.",
        detalhes={"armadilha_id": str(armadilha_id)},
    )


@router.put(
    "/{armadilha_id}/foto",
    response_model=FotoSaida,
    responses=respostas_de_erro(
        CodigoErro.ARQUIVO_AUSENTE,
        CodigoErro.FORMATO_NAO_SUPORTADO,
        CodigoErro.RESOLUCAO_INSUFICIENTE,
        CodigoErro.ARQUIVO_MUITO_GRANDE,
        CodigoErro.ARMADILHA_NAO_ENCONTRADA,
        CodigoErro.VALIDACAO_FALHOU,
        CodigoErro.ERRO_INTERNO,
    ),
)
async def enviar_foto(
    armadilha_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    arquivo: Annotated[UploadFile | None, File()] = None,
) -> FotoSaida:
    """Valida a imagem, guarda só a cópia reduzida e sem metadados.

    Args:
        armadilha_id: UUID da armadilha que recebe a foto.
        session: sessão da requisição.
        arquivo: imagem JPEG ou PNG de até 4 MB.

    Returns:
        O tipo ``real`` e a URL versionada da foto.

    Raises:
        ErroDeApi: se o arquivo for inválido ou a armadilha não existir.
    """
    if arquivo is None:
        raise ErroDeApi(
            CodigoErro.ARQUIVO_AUSENTE,
            "Envie uma imagem para continuar.",
            detalhes={"campo": "arquivo"},
        )
    conteudo = await ler_upload_limitado(arquivo)
    imagem = await validar_upload_imagem(conteudo)
    reduzida = await asyncio.to_thread(preparar_foto, imagem.conteudo)
    agora = datetime.now(timezone.utc)

    def gravar() -> None:
        armadilha = ArmadilhaRepository(session).definir_foto(
            armadilha_id, reduzida, agora
        )
        if armadilha is None:
            raise _erro_armadilha(armadilha_id)
        session.commit()

    try:
        await asyncio.to_thread(gravar)
    except Exception:
        session.rollback()
        raise
    return FotoSaida(foto_tipo="real", foto_url=url_da_foto(armadilha_id, agora))


@router.delete(
    "/{armadilha_id}/foto",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=respostas_de_erro(
        CodigoErro.ARMADILHA_NAO_ENCONTRADA,
        CodigoErro.VALIDACAO_FALHOU,
    ),
)
def remover_foto(
    armadilha_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    """Volta à foto padrão do modelo; repetir a chamada não causa erro."""
    if ArmadilhaRepository(session).remover_foto(armadilha_id) is None:
        raise _erro_armadilha(armadilha_id)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{armadilha_id}/foto",
    responses=respostas_de_erro(
        CodigoErro.ARMADILHA_NAO_ENCONTRADA,
        CodigoErro.VALIDACAO_FALHOU,
    ),
)
def obter_foto(
    request: Request,
    armadilha_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    """Serve a cópia reduzida; responde 404 sem foto real ou sem armadilha."""
    foto = ArmadilhaRepository(session).obter_foto(armadilha_id)
    if foto is None:
        raise ErroDeApi(
            CodigoErro.ARMADILHA_NAO_ENCONTRADA,
            "A armadilha não possui foto de identificação.",
            detalhes={"armadilha_id": str(armadilha_id)},
        )
    conteudo, atualizada_em = foto
    resposta = Response(
        content=conteudo,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "private, max-age=31536000, immutable",
            "Content-Disposition": "inline",
            "ETag": f'"{hashlib.sha256(conteudo).hexdigest()}"',
            "Last-Modified": format_datetime(
                atualizada_em.astimezone(timezone.utc), usegmt=True
            ),
            "X-Content-Type-Options": "nosniff",
        },
    )
    if requisicao_nao_modificada(request, resposta):
        return Response(
            status_code=304,
            headers={
                nome: valor
                for nome, valor in resposta.headers.items()
                if nome.lower() != "content-length"
            },
        )
    return resposta
