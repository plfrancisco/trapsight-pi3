"""Endpoints de envio e consulta individual de análises de imagem."""

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime
from pathlib import Path
from stat import S_ISREG
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from src.api.dependencias import get_agora, get_inferidor, get_session, get_settings
from src.api.erros import CodigoErro, ErroDeApi, respostas_de_erro
from src.api.schemas.analise import AnaliseSaida
from src.config.settings import Settings
from src.entities import Analise, Armadilha, Refil, StatusAnalise
from src.inference.contrato import (
    ErroDeInferencia,
    Inferidor,
    PlacaNaoDetectada,
    ResultadoInferencia,
)
from src.repositories.analise_repository import AnaliseRepository
from src.repositories.armadilha_repository import ArmadilhaRepository
from src.repositories.refil_repository import RefilRepository
from src.services import armazenamento
from src.services.upload import (
    LIMITE_TAMANHO_UPLOAD_BYTES,
    TAMANHO_BLOCO_UPLOAD_BYTES,
    ArquivoMuitoGrande,
    FormatoNaoSuportado,
    ImagemValidada,
    ResolucaoInsuficiente,
    validar_imagem,
)

router = APIRouter(prefix="/analises", tags=["Análises"])
TEMPO_LIMITE_INFERENCIA_SEGUNDOS = 30
logger = logging.getLogger(__name__)


@router.post(
    "",
    response_model=AnaliseSaida,
    status_code=status.HTTP_201_CREATED,
    responses=respostas_de_erro(
        CodigoErro.ARQUIVO_AUSENTE,
        CodigoErro.FORMATO_NAO_SUPORTADO,
        CodigoErro.RESOLUCAO_INSUFICIENTE,
        CodigoErro.ARQUIVO_MUITO_GRANDE,
        CodigoErro.ARMADILHA_NAO_ENCONTRADA,
        CodigoErro.REFIL_ATIVO_INEXISTENTE,
        CodigoErro.PLACA_NAO_DETECTADA,
        CodigoErro.FALHA_INFERENCIA,
        CodigoErro.VALIDACAO_FALHOU,
        CodigoErro.REQUISICAO_INVALIDA,
        CodigoErro.ERRO_INTERNO,
    ),
)
# Escolhemos manter o endpoint async para ler UploadFile e aguardar a inferência
# com timeout; consultas SQL, Pillow e filesystem síncronos rodam em threads para
# não bloquear o event loop durante consultas ou gravações com fsync.
async def criar_analise(
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    agora: Annotated[datetime, Depends(get_agora)],
    inferidor: Annotated[Inferidor, Depends(get_inferidor)],
    armadilha_id: Annotated[UUID, Form()],
    imagem: Annotated[UploadFile | None, File()] = None,
) -> AnaliseSaida:
    """Valida, armazena e analisa uma imagem em um único fluxo transacional.

    Args:
        session: sessão que mantém a gravação do resultado em uma transação.
        settings: configuração com o diretório autorizado para uploads.
        agora: instante UTC usado para registrar a análise.
        inferidor: implementação síncrona de inferência ativa na aplicação.
        armadilha_id: armadilha indicada no formulário multipart.
        imagem: arquivo opcional para que sua ausência receba o código próprio.

    Returns:
        Resultado persistido da análise com URLs dos binários.

    Raises:
        ErroDeApi: quando o arquivo ou o estado da armadilha for inválido.
    """
    if imagem is None:
        raise ErroDeApi(
            CodigoErro.ARQUIVO_AUSENTE,
            "Envie uma imagem para continuar.",
            detalhes={"campo": "imagem"},
        )

    conteudo = await ler_upload_limitado(imagem)
    imagem_validada = await validar_upload_imagem(conteudo)

    armadilha, refil = await asyncio.to_thread(
        _buscar_armadilha_e_refil,
        session,
        armadilha_id,
    )
    if armadilha is None:
        raise _erro_armadilha_nao_encontrada(armadilha_id)
    if refil is None:
        raise ErroDeApi(
            CodigoErro.REFIL_ATIVO_INEXISTENTE,
            "A armadilha não possui refil ativo.",
            detalhes={"armadilha_id": str(armadilha_id)},
        )

    analise_id = uuid4()
    armazenar_no_banco = settings.storage_backend == "database"
    imagem_original: bytes | None = None
    mascara: bytes | None = None
    try:
        if armazenar_no_banco:
            caminho_imagem = f"{analise_id}/original.{imagem_validada.extensao}"
        else:
            caminho_imagem = await asyncio.to_thread(
                armazenamento.gravar_imagem_original,
                settings.uploads_dir,
                analise_id,
                imagem_validada.conteudo,
                imagem_validada.extensao,
            )
        resultado = await _executar_inferencia(inferidor, imagem_validada.conteudo)
        if armazenar_no_banco:
            imagem_original = imagem_validada.conteudo
            mascara = resultado.mascara
        else:
            await asyncio.to_thread(
                armazenamento.gravar_mascara,
                settings.uploads_dir,
                analise_id,
                resultado.mascara,
            )
        resposta = await asyncio.to_thread(
            _persistir_analise,
            session,
            analise_id,
            refil.id,
            armadilha_id,
            agora,
            resultado,
            caminho_imagem,
            imagem_original,
            mascara,
        )
    except BaseException:
        # Cancelamentos também precisam reverter a linha e a mídia já gravada.
        try:
            await asyncio.to_thread(session.rollback)
        finally:
            if not armazenar_no_banco:
                await asyncio.to_thread(
                    armazenamento.remover_arquivos_analise,
                    settings.uploads_dir,
                    analise_id,
                )
        raise

    return resposta


@router.get(
    "/{analise_id}",
    response_model=AnaliseSaida,
    responses=respostas_de_erro(
        CodigoErro.ANALISE_NAO_ENCONTRADA,
        CodigoErro.VALIDACAO_FALHOU,
        CodigoErro.ERRO_INTERNO,
    ),
)
def obter_analise(
    analise_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> AnaliseSaida:
    """Busca uma análise pelo UUID e devolve o mesmo formato do cadastro.

    Args:
        analise_id: UUID da análise consultada.
        session: sessão usada para carregar a análise e seu refil.

    Returns:
        Análise persistida com as mesmas URLs expostas pelo POST.

    Raises:
        ErroDeApi: se o UUID não corresponder a uma análise persistida.
    """
    analise = AnaliseRepository(session).get_by_id(analise_id)
    if analise is None:
        raise ErroDeApi(
            CodigoErro.ANALISE_NAO_ENCONTRADA,
            "A análise solicitada não foi encontrada.",
            detalhes={"analise_id": str(analise_id)},
        )
    return _montar_saida(analise, analise.refil.armadilha_id)


@router.get(
    "/{analise_id}/imagem",
    response_class=FileResponse,
    responses=respostas_de_erro(
        CodigoErro.ANALISE_NAO_ENCONTRADA,
        CodigoErro.VALIDACAO_FALHOU,
    ),
)
def obter_imagem_analise(
    request: Request,
    analise_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """Serve a imagem original da análise como arquivo protegido.

    Args:
        request: requisição usada para avaliar cabeçalhos condicionais.
        analise_id: UUID da análise solicitada.
        session: sessão usada para buscar a análise.
        settings: configuração que define a raiz dos arquivos autorizados.

    Returns:
        Arquivo JPEG ou PNG em streaming, ou resposta 304 sem corpo.

    Raises:
        ErroDeApi: se a análise ou seu arquivo não estiver disponível.
    """
    return _servir_recurso_analise(
        request,
        analise_id,
        session,
        settings,
        recurso="imagem",
    )


@router.get(
    "/{analise_id}/mascara",
    response_class=FileResponse,
    responses=respostas_de_erro(
        CodigoErro.ANALISE_NAO_ENCONTRADA,
        CodigoErro.VALIDACAO_FALHOU,
    ),
)
def obter_mascara_analise(
    request: Request,
    analise_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """Serve a máscara PNG derivada do UUID da análise, sem usar caminho do banco.

    Args:
        request: requisição usada para avaliar cabeçalhos condicionais.
        analise_id: UUID da análise solicitada.
        session: sessão usada para confirmar que a análise existe.
        settings: configuração que define a raiz dos arquivos autorizados.

    Returns:
        Máscara PNG em streaming, ou resposta 304 sem corpo.

    Raises:
        ErroDeApi: se a análise ou sua máscara não estiver disponível.
    """
    return _servir_recurso_analise(
        request,
        analise_id,
        session,
        settings,
        recurso="mascara",
    )


def _servir_recurso_analise(
    request: Request,
    analise_id: UUID,
    session: Session,
    settings: Settings,
    *,
    recurso: Literal["imagem", "mascara"],
) -> Response:
    """Valida o registro e o caminho antes de criar a resposta de arquivo."""
    analise = AnaliseRepository(session).get_by_id(analise_id)
    if analise is None:
        raise ErroDeApi(
            CodigoErro.ANALISE_NAO_ENCONTRADA,
            "A análise solicitada não foi encontrada.",
            detalhes={"analise_id": str(analise_id)},
        )

    if recurso == "imagem":
        caminho_salvo = analise.caminho_imagem
        try:
            extensao = Path(caminho_salvo).suffix.lower().lstrip(".")
        except (TypeError, ValueError):
            raise _erro_recurso_analise(analise_id, recurso) from None
        tipos_por_extensao = {"jpg": "image/jpeg", "png": "image/png"}
        tipo_midia = tipos_por_extensao.get(extensao)
        if tipo_midia is None:
            raise _erro_recurso_analise(analise_id, recurso)
    else:
        caminho_salvo = f"{analise_id}/mascara.png"
        tipo_midia = "image/png"

    if settings.storage_backend == "database":
        conteudo = analise.imagem_original if recurso == "imagem" else analise.mascara
        if not conteudo:
            raise _erro_recurso_analise(analise_id, recurso)
        conteudo = bytes(conteudo)
        instante = analise.analisado_em
        if instante.tzinfo is None:
            instante = instante.replace(tzinfo=timezone.utc)
        resposta = Response(
            content=conteudo,
            media_type=tipo_midia,
            headers={
                "Cache-Control": "private, max-age=31536000, immutable",
                "Content-Disposition": "inline",
                "ETag": f'"{hashlib.sha256(conteudo).hexdigest()}"',
                "Last-Modified": format_datetime(
                    instante.astimezone(timezone.utc), usegmt=True
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

    try:
        caminho = armazenamento.resolver_caminho_arquivo(
            settings.uploads_dir,
            caminho_salvo,
        )
        metadados = caminho.stat()
        if not S_ISREG(metadados.st_mode):
            raise ValueError("O recurso precisa ser um arquivo regular.")
    except (OSError, RuntimeError, TypeError, ValueError):
        raise _erro_recurso_analise(analise_id, recurso) from None

    resposta = FileResponse(
        caminho,
        media_type=tipo_midia,
        headers={
            "Cache-Control": "private, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
        },
        stat_result=metadados,
    )
    if requisicao_nao_modificada(request, resposta):
        return Response(
            status_code=304,
            headers=dict(resposta.headers.items()),
        )
    return resposta


def _erro_recurso_analise(
    analise_id: UUID,
    recurso: Literal["imagem", "mascara"],
) -> ErroDeApi:
    """Registra a indisponibilidade da mídia sem incluir caminhos no erro público."""
    logger.warning(
        "Arquivo de análise ausente ou inválido (analise_id=%s, recurso=%s).",
        analise_id,
        recurso,
    )
    return ErroDeApi(
        CodigoErro.ANALISE_NAO_ENCONTRADA,
        "O arquivo solicitado não foi encontrado.",
        detalhes={"recurso": recurso},
    )


def requisicao_nao_modificada(request: Request, resposta: Response) -> bool:
    """Aplica validadores GET para evitar reenviar um arquivo imutável."""
    etag_atual = resposta.headers["etag"]
    etag_solicitado = request.headers.get("if-none-match")
    if etag_solicitado is not None:
        for candidato in etag_solicitado.split(","):
            candidato = candidato.strip()
            if candidato == "*":
                return True
            if candidato.startswith("W/"):
                candidato = candidato[2:]
            if candidato == etag_atual:
                return True
        return False

    data_solicitada = request.headers.get("if-modified-since")
    if data_solicitada is None:
        return False
    try:
        instante = parsedate_to_datetime(data_solicitada)
    except (TypeError, ValueError, OverflowError):
        return False
    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=timezone.utc)
    ultima_modificacao = parsedate_to_datetime(
        resposta.headers["last-modified"]
    ).astimezone(timezone.utc)
    return ultima_modificacao.replace(microsecond=0) <= instante.astimezone(
        timezone.utc
    ).replace(microsecond=0)


async def validar_upload_imagem(conteudo: bytes) -> ImagemValidada:
    """Valida o conteúdo real e traduz as falhas para erros públicos da API.

    Args:
        conteudo: bytes já limitados do arquivo recebido.

    Returns:
        Imagem validada, com a extensão deduzida do formato real.

    Raises:
        ErroDeApi: se o formato, a resolução ou o total de pixels forem inválidos.
    """
    try:
        return await asyncio.to_thread(validar_imagem, conteudo)
    except ArquivoMuitoGrande:
        raise ErroDeApi(
            CodigoErro.ARQUIVO_MUITO_GRANDE,
            "A imagem tem resolução alta demais.",
            detalhes={"motivo": "pixels"},
        ) from None
    except FormatoNaoSuportado:
        raise ErroDeApi(
            CodigoErro.FORMATO_NAO_SUPORTADO,
            "Envie uma imagem JPEG ou PNG válida.",
        ) from None
    except ResolucaoInsuficiente:
        raise ErroDeApi(
            CodigoErro.RESOLUCAO_INSUFICIENTE,
            "A imagem precisa ter ao menos 512 pixels no maior lado.",
        ) from None


async def ler_upload_limitado(arquivo: UploadFile) -> bytes:
    """Lê blocos multipart na camada HTTP e rejeita o primeiro byte excedente."""
    partes: list[bytes] = []
    total = 0
    while True:
        bloco = await arquivo.read(
            min(TAMANHO_BLOCO_UPLOAD_BYTES, LIMITE_TAMANHO_UPLOAD_BYTES + 1 - total)
        )
        if not bloco:
            return b"".join(partes)
        total += len(bloco)
        if total > LIMITE_TAMANHO_UPLOAD_BYTES:
            raise ErroDeApi(
                CodigoErro.ARQUIVO_MUITO_GRANDE,
                "O arquivo enviado excede o tamanho permitido.",
                detalhes={"motivo": "bytes"},
            )
        partes.append(bloco)


def _buscar_armadilha_e_refil(
    session: Session,
    armadilha_id: UUID,
) -> tuple[Armadilha | None, Refil | None]:
    """Executa as consultas SQL síncronas da análise na mesma thread de trabalho."""
    armadilha = ArmadilhaRepository(session).get_by_id_ativo(armadilha_id)
    refil = (
        None
        if armadilha is None
        else RefilRepository(session).get_active_for_armadilha(armadilha_id)
    )
    return armadilha, refil


def _persistir_analise(
    session: Session,
    analise_id: UUID,
    refil_id: UUID,
    armadilha_id: UUID,
    agora: datetime,
    resultado: ResultadoInferencia,
    caminho_imagem: str,
    imagem_original: bytes | None = None,
    mascara: bytes | None = None,
) -> AnaliseSaida:
    """Grava e confirma a análise sem executar I/O de banco no event loop."""
    analise = AnaliseRepository(session).create(
        analise_id=analise_id,
        refil_id=refil_id,
        analisado_em=agora,
        percentual_coberto=resultado.percentual_coberto,
        status=resultado.status,
        caminho_imagem=caminho_imagem,
        modelo_versao=resultado.modelo_versao,
        imagem_original=imagem_original,
        mascara=mascara,
    )
    resposta = _montar_saida(analise, armadilha_id)
    session.commit()
    return resposta


async def _executar_inferencia(
    inferidor: Inferidor,
    conteudo: bytes,
) -> ResultadoInferencia:
    """Executa o inferidor síncrono em uma thread com tempo máximo fixo.

    Args:
        inferidor: implementação ativa no estado da aplicação.
        conteudo: bytes da imagem previamente validados.

    Returns:
        Resultado calculado pelo inferidor.

    Raises:
        ErroDeApi: para timeout ou falha de inferência conhecida.
    """
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(inferidor.inferir, conteudo),
            timeout=TEMPO_LIMITE_INFERENCIA_SEGUNDOS,
        )
    except TimeoutError:
        raise ErroDeApi(
            CodigoErro.FALHA_INFERENCIA,
            "A análise não pôde ser concluída no tempo permitido.",
        ) from None
    except PlacaNaoDetectada:
        raise ErroDeApi(
            CodigoErro.PLACA_NAO_DETECTADA,
            "A superfície adesiva não foi localizada na imagem.",
        ) from None
    except ErroDeInferencia:
        raise ErroDeApi(
            CodigoErro.FALHA_INFERENCIA,
            "A análise não pôde ser concluída.",
        ) from None


def _montar_saida(analise: Analise, armadilha_id: UUID) -> AnaliseSaida:
    """Constrói os links sem depender de arquivos ou dados fornecidos pelo cliente."""
    return AnaliseSaida(
        id=analise.id,
        refil_id=analise.refil_id,
        armadilha_id=armadilha_id,
        analisado_em=analise.analisado_em,
        percentual_coberto=analise.percentual_coberto,
        status=StatusAnalise(analise.status),
        modelo_versao=analise.modelo_versao,
        imagem_url=f"/api/analises/{analise.id}/imagem",
        mascara_url=f"/api/analises/{analise.id}/mascara",
    )


def _erro_armadilha_nao_encontrada(armadilha_id: UUID) -> ErroDeApi:
    """Cria o erro de domínio público para uma armadilha inexistente."""
    return ErroDeApi(
        CodigoErro.ARMADILHA_NAO_ENCONTRADA,
        "A armadilha solicitada não foi encontrada.",
        detalhes={"armadilha_id": str(armadilha_id)},
    )
