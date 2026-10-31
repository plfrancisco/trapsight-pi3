"""Reduz e saneia a foto de identificação enviada para uma armadilha."""

from datetime import datetime, timezone
from io import BytesIO
from uuid import UUID

from PIL import Image, ImageOps

LADO_MAXIMO_FOTO_PX = 800
QUALIDADE_JPEG_FOTO = 85


def preparar_foto(conteudo: bytes) -> bytes:
    """Gera a cópia guardada: JPEG de até 800 px no maior lado, sem metadados.

    O conteúdo já passou por ``validar_imagem``. A orientação do EXIF é aplicada
    antes de descartá-lo, para a foto não aparecer girada, e nenhum metadado
    (localização, câmera, data) é regravado: o JPEG sai sem EXIF nem perfil ICC.

    Args:
        conteudo: bytes de uma imagem JPEG ou PNG validada.

    Returns:
        JPEG reduzido em bytes.
    """
    with Image.open(BytesIO(conteudo)) as origem:
        imagem = ImageOps.exif_transpose(origem)
        if imagem.mode in ("RGBA", "LA", "P"):
            quadro = imagem.convert("RGBA")
            fundo = Image.new("RGB", quadro.size, (255, 255, 255))
            fundo.paste(quadro, mask=quadro.getchannel("A"))
            imagem = fundo
        else:
            imagem = imagem.convert("RGB")
        imagem.thumbnail((LADO_MAXIMO_FOTO_PX, LADO_MAXIMO_FOTO_PX), Image.LANCZOS)
        saida = BytesIO()
        imagem.save(saida, format="JPEG", quality=QUALIDADE_JPEG_FOTO, optimize=True)
    return saida.getvalue()


def url_da_foto(armadilha_id: UUID, atualizada_em: datetime) -> str:
    """Monta o caminho relativo com a versão que invalida o cache do navegador."""
    versao = int(atualizada_em.astimezone(timezone.utc).timestamp() * 1000)
    return f"/api/armadilhas/{armadilha_id}/foto?v={versao}"
