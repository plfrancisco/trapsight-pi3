"""Valida e limita imagens recebidas antes do processamento da análise."""

import struct
from dataclasses import dataclass
from io import BytesIO

from PIL import Image

from src.inference.contrato import LIMITE_PIXELS_IMAGEM

LIMITE_TAMANHO_UPLOAD_BYTES = 10 * 1024 * 1024
TAMANHO_BLOCO_UPLOAD_BYTES = 64 * 1024
RESOLUCAO_MINIMA_IMAGEM = 512

_ASSINATURA_JPEG = b"\xff\xd8\xff"
_ASSINATURA_PNG = b"\x89PNG\r\n\x1a\n"
_MENSAGEM_ARQUIVO_GRANDE = "O arquivo enviado excede o tamanho permitido."
_MENSAGEM_FORMATO_INVALIDO = "Envie uma imagem JPEG ou PNG válida."


class ArquivoMuitoGrande(Exception):
    """Indica que o conteúdo ou as dimensões excedem o limite aceito."""


class FormatoNaoSuportado(Exception):
    """Indica que o conteúdo não é uma imagem JPEG ou PNG íntegra."""


class ResolucaoInsuficiente(Exception):
    """Indica que a imagem não alcança a resolução mínima aceita."""


@dataclass(frozen=True, slots=True)
class ImagemValidada:
    """Bytes e metadados derivados de uma imagem efetivamente decodificável."""

    conteudo: bytes
    extensao: str
    largura: int
    altura: int


def validar_imagem(conteudo: bytes) -> ImagemValidada:
    """Valida conteúdo, dimensões e decodificação sem confiar nos metadados HTTP.

    Args:
        conteudo: bytes já limitados do arquivo recebido.

    Returns:
        Imagem validada com extensão deduzida do formato real.

    Raises:
        FormatoNaoSuportado: se o formato ou os dados decodificados forem inválidos.
        ResolucaoInsuficiente: se a imagem não alcançar a resolução mínima.
        ArquivoMuitoGrande: se o conteúdo exceder um dos limites aceitos.
    """
    if conteudo.startswith(_ASSINATURA_JPEG):
        formato_esperado = "JPEG"
        extensao = "jpg"
    elif conteudo.startswith(_ASSINATURA_PNG):
        formato_esperado = "PNG"
        extensao = "png"
    else:
        raise FormatoNaoSuportado(_MENSAGEM_FORMATO_INVALIDO)

    try:
        with Image.open(BytesIO(conteudo)) as imagem:
            if imagem.format != formato_esperado:
                raise FormatoNaoSuportado(_MENSAGEM_FORMATO_INVALIDO)
            largura, altura = imagem.size
            _validar_dimensoes(largura, altura)
            imagem.verify()

        # verify() checa a estrutura; load() também detecta dados truncados.
        with Image.open(BytesIO(conteudo)) as imagem:
            imagem.load()
    except (ArquivoMuitoGrande, FormatoNaoSuportado, ResolucaoInsuficiente):
        raise
    except Image.DecompressionBombError:
        raise ArquivoMuitoGrande(_MENSAGEM_ARQUIVO_GRANDE) from None
    except (
        EOFError,
        IndexError,
        OSError,
        OverflowError,
        SyntaxError,
        ValueError,
        struct.error,
    ):
        raise FormatoNaoSuportado(_MENSAGEM_FORMATO_INVALIDO) from None

    return ImagemValidada(
        conteudo=conteudo,
        extensao=extensao,
        largura=largura,
        altura=altura,
    )


def _validar_dimensoes(largura: int, altura: int) -> None:
    """Aplica os tetos antes de decodificar pixels para reduzir risco de exaustão."""
    if largura <= 0 or altura <= 0:
        raise FormatoNaoSuportado(_MENSAGEM_FORMATO_INVALIDO)
    if largura * altura > LIMITE_PIXELS_IMAGEM:
        raise ArquivoMuitoGrande(_MENSAGEM_ARQUIVO_GRANDE)
    if max(largura, altura) < RESOLUCAO_MINIMA_IMAGEM:
        raise ResolucaoInsuficiente(
            "A imagem precisa ter ao menos 512 pixels no maior lado."
        )
