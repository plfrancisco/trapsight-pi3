"""Implementação provisória determinística para o contrato de inferência."""

from decimal import Decimal
from io import BytesIO

from PIL import Image, ImageDraw

from src.inference.contrato import (
    FalhaInferencia,
    ResultadoInferencia,
    validar_versao_semver,
)
from src.inference.status import derivar_status

# Vinte milhões de pixels limita a expansão em memória sem excluir fotos comuns.
LIMITE_PIXELS_IMAGEM = 20_000_000
_PERCENTUAL_STUB = Decimal("55.00")
_HASH_STUB = "00000000"
_MENSAGEM_IMAGEM_INVALIDA = "A imagem não pôde ser processada."


class InferidorStub:
    """Implementação provisória que devolve valores fixos no contrato real.

    Args:
        modelo_versao: Versão semântica configurada para o modelo.
        limiar_atencao: Percentual a partir do qual começa o estado de atenção.
        limiar_trocar: Percentual limite do estado de atenção.

    Raises:
        ValueError: Se a versão configurada não seguir SemVer.
    """

    def __init__(
        self,
        modelo_versao: str,
        limiar_atencao: Decimal,
        limiar_trocar: Decimal,
    ) -> None:
        validar_versao_semver(modelo_versao)
        self._modelo_versao = modelo_versao
        self._limiar_atencao = limiar_atencao
        self._limiar_trocar = limiar_trocar

    def inferir(self, imagem: bytes) -> ResultadoInferencia:
        """Cria resultado fixo e máscara para uma imagem decodificável.

        Args:
            imagem: Conteúdo binário da imagem original.

        Returns:
            Resultado de cobertura com uma máscara PNG na resolução de entrada.

        Raises:
            FalhaInferencia: Se os bytes forem inválidos, truncados ou grandes demais.
        """
        try:
            mascara = self._criar_mascara(imagem)
        except FalhaInferencia:
            raise
        except Exception:
            raise FalhaInferencia(_MENSAGEM_IMAGEM_INVALIDA) from None

        return ResultadoInferencia(
            percentual_coberto=_PERCENTUAL_STUB,
            status=derivar_status(
                _PERCENTUAL_STUB,
                self._limiar_atencao,
                self._limiar_trocar,
            ),
            modelo_versao=f"{self._modelo_versao}+{_HASH_STUB}",
            mascara=mascara,
        )

    @staticmethod
    def _criar_mascara(imagem: bytes) -> bytes:
        """Sobrepõe a faixa fixa após validar e decodificar a imagem de entrada."""
        try:
            with Image.open(BytesIO(imagem)) as original:
                largura, altura = original.size
                if largura <= 0 or altura <= 0:
                    raise FalhaInferencia(_MENSAGEM_IMAGEM_INVALIDA)
                if largura * altura > LIMITE_PIXELS_IMAGEM:
                    raise FalhaInferencia(_MENSAGEM_IMAGEM_INVALIDA)

                original.load()
                base = original.convert("RGBA")
        except Image.DecompressionBombError:
            raise FalhaInferencia(_MENSAGEM_IMAGEM_INVALIDA) from None

        altura_faixa = max(
            1,
            int(Decimal(altura) * _PERCENTUAL_STUB / Decimal("100")),
        )
        sobreposicao = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
        desenho = ImageDraw.Draw(sobreposicao)
        desenho.rectangle(
            (0, 0, largura - 1, altura_faixa - 1),
            fill=(255, 0, 255, 102),
        )
        resultado = Image.alpha_composite(base, sobreposicao)

        buffer = BytesIO()
        resultado.save(buffer, format="PNG", optimize=False)
        return buffer.getvalue()
