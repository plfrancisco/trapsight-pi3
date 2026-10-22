"""Testes isolados das regras de leitura e validação de imagens."""

import asyncio
import struct
import zlib
from io import BytesIO

import pytest
from PIL import Image

from src.api.erros import CodigoErro, ErroDeApi
from src.api.rotas.analises import _ler_upload_limitado
from src.inference.contrato import LIMITE_PIXELS_IMAGEM
from src.services.upload import (
    LIMITE_TAMANHO_UPLOAD_BYTES,
    ArquivoMuitoGrande,
    FormatoNaoSuportado,
    ResolucaoInsuficiente,
    validar_imagem,
)


def _imagem(tamanho: tuple[int, int], formato: str) -> bytes:
    """Gera uma imagem determinística em memória sem acessar serviços externos."""
    buffer = BytesIO()
    Image.new("RGB", tamanho, (24, 82, 120)).save(buffer, format=formato)
    return buffer.getvalue()


class _ArquivoEmMemoria:
    """Simula leituras assíncronas de um arquivo recebido em blocos."""

    def __init__(self, conteudo: bytes) -> None:
        self._buffer = BytesIO(conteudo)

    async def read(self, tamanho: int) -> bytes:
        """Devolve no máximo o bloco solicitado pelo serviço de upload."""
        return self._buffer.read(tamanho)


@pytest.mark.parametrize(
    ("formato", "extensao"),
    [("JPEG", "jpg"), ("PNG", "png")],
)
def test_validar_imagem_identifica_o_formato_real(
    formato: str,
    extensao: str,
) -> None:
    imagem = validar_imagem(_imagem((512, 768), formato))

    assert imagem.extensao == extensao
    assert (imagem.largura, imagem.altura) == (512, 768)


@pytest.mark.parametrize(
    ("conteudo", "excecao"),
    [
        (b"texto simples", FormatoNaoSuportado),
        (b"\xff\xd8\xff" + b"dados truncados", FormatoNaoSuportado),
        (_imagem((100, 100), "PNG"), ResolucaoInsuficiente),
    ],
)
def test_validar_imagem_rejeita_conteudo_invalido_ou_pequeno(
    conteudo: bytes,
    excecao: type[Exception],
) -> None:
    with pytest.raises(excecao):
        validar_imagem(conteudo)


def test_leitura_limitada_aceita_ate_dez_mib_e_rejeita_o_byte_seguinte() -> None:
    aceito = asyncio.run(
        _ler_upload_limitado(_ArquivoEmMemoria(b"x" * LIMITE_TAMANHO_UPLOAD_BYTES))
    )
    assert len(aceito) == LIMITE_TAMANHO_UPLOAD_BYTES

    with pytest.raises(ErroDeApi) as erro:
        asyncio.run(
            _ler_upload_limitado(
                _ArquivoEmMemoria(b"x" * (LIMITE_TAMANHO_UPLOAD_BYTES + 1))
            )
        )

    assert erro.value.codigo is CodigoErro.ARQUIVO_MUITO_GRANDE


def test_imagem_acima_do_teto_de_pixels_e_rejeitada_antes_de_decodificar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conteudo = bytearray(_imagem((1, 1), "PNG"))
    conteudo[16:20] = struct.pack(">I", LIMITE_PIXELS_IMAGEM + 1)
    conteudo[20:24] = struct.pack(">I", 1)
    conteudo[29:33] = struct.pack(">I", zlib.crc32(conteudo[12:29]) & 0xFFFFFFFF)

    def falhar_se_decodificar(_imagem: Image.Image) -> None:
        raise AssertionError("O cabeçalho deve ser rejeitado antes da decodificação.")

    monkeypatch.setattr(Image.Image, "load", falhar_se_decodificar)
    with pytest.raises(ArquivoMuitoGrande):
        validar_imagem(bytes(conteudo))
