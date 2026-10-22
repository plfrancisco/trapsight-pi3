"""Inferência da placa com o checkpoint treinado."""

from __future__ import annotations

import hashlib
import math
import threading
from decimal import ROUND_HALF_UP, Decimal
from io import BytesIO
from logging import getLogger
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from src.inference.contrato import (
    LIMITE_PIXELS_IMAGEM,
    FalhaInferencia,
    PlacaNaoDetectada,
    ResultadoInferencia,
    validar_versao_semver,
)
from src.inference.status import derivar_status

_LARGURA_ENTRADA = 768
_ALTURA_ENTRADA = 576
_NUMERO_CLASSES = 3
_MEDIA_IMAGENET = (0.485, 0.456, 0.406)
_DESVIO_IMAGENET = (0.229, 0.224, 0.225)
_CLASSES = ("fundo", "placa_limpa", "placa_coberta")
_AREA_MINIMA_PLACA = 0.05
_OPACIDADE_MASCARA = 102
_MENSAGEM_IMAGEM_INVALIDA = "A imagem não pôde ser processada."
logger = getLogger(__name__)


class InferidorModelo:
    """Carrega uma U-Net em CPU e segmenta as imagens recebidas.

    Args:
        caminho_pesos: Caminho do checkpoint gravado pelo pipeline de treino.
        modelo_versao: Versão SemVer configurada para o modelo.
        limiar_atencao: Percentual a partir do qual começa o estado de atenção.
        limiar_trocar: Percentual limite superior do estado de atenção.
        threads: Número máximo de threads intraoperacionais do PyTorch.

    Raises:
        RuntimeError: Se o checkpoint ou as dependências de inferência forem inválidos.
        ValueError: Se a versão configurada não seguir SemVer.
    """

    def __init__(
        self,
        caminho_pesos: str | Path,
        modelo_versao: str,
        limiar_atencao: Decimal,
        limiar_trocar: Decimal,
        threads: int = 1,
    ) -> None:
        validar_versao_semver(modelo_versao)
        if threads < 1:
            raise ValueError("O número de threads de inferência deve ser positivo.")

        try:
            import segmentation_models_pytorch as smp
            import torch
        except ImportError as erro:
            raise RuntimeError(
                "As dependências de inferência estão ausentes. "
                "Instale o grupo `inference` do backend."
            ) from erro

        self._torch = torch
        self._limiar_atencao = limiar_atencao
        self._limiar_trocar = limiar_trocar
        self._lock = threading.Lock()
        self._caminho_pesos = Path(caminho_pesos)
        self._hash_pesos = self._calcular_hash_pesos(self._caminho_pesos)
        torch.set_num_threads(threads)

        checkpoint = self._carregar_checkpoint(torch, self._caminho_pesos)
        arquitetura = checkpoint["arquitetura"]
        construtor = getattr(smp, arquitetura["nome"], None)
        if not callable(construtor):
            raise RuntimeError(
                f"Arquitetura de segmentação desconhecida no checkpoint: "
                f"{arquitetura['nome']}."
            )

        try:
            modelo = construtor(
                encoder_name=arquitetura["encoder"],
                encoder_weights=None,
                in_channels=3,
                classes=_NUMERO_CLASSES,
            )
            modelo.load_state_dict(checkpoint["state_dict"], strict=True)
            self._modelo = modelo.to("cpu").eval()
        except Exception as erro:
            raise RuntimeError(
                "O checkpoint contém pesos incompatíveis com a arquitetura declarada."
            ) from erro

        self._media = torch.tensor(_MEDIA_IMAGENET, dtype=torch.float32).view(
            1, 3, 1, 1
        )
        self._desvio = torch.tensor(_DESVIO_IMAGENET, dtype=torch.float32).view(
            1, 3, 1, 1
        )
        self._modelo_versao = f"{modelo_versao}+{self._hash_pesos}"
        self._aquecimento()

    @staticmethod
    def _calcular_hash_pesos(caminho: Path) -> str:
        """Calcula os oito primeiros dígitos do SHA-256 do arquivo de pesos."""
        resumo = hashlib.sha256()
        try:
            with caminho.open("rb") as arquivo:
                for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
                    resumo.update(bloco)
        except FileNotFoundError:
            raise RuntimeError(
                f"Checkpoint do modelo não encontrado: {caminho}."
            ) from None
        except OSError:
            raise RuntimeError(f"Checkpoint do modelo ilegível: {caminho}.") from None
        return resumo.hexdigest()[:8]

    @staticmethod
    def _carregar_checkpoint(torch: Any, caminho: Path) -> dict[str, Any]:
        """Lê e valida o formato e os metadados usados pelo treinamento."""
        try:
            bruto = torch.load(caminho, weights_only=True, map_location="cpu")
        except Exception:
            raise RuntimeError(f"Checkpoint do modelo inválido: {caminho}.") from None

        if not isinstance(bruto, dict):
            raise RuntimeError("Checkpoint inválido: esperado um objeto de metadados.")

        chaves_obrigatorias = {
            "state_dict",
            "arquitetura",
            "entrada",
            "normalizacao",
            "classes",
        }
        ausentes = chaves_obrigatorias - bruto.keys()
        if ausentes:
            nomes = ", ".join(sorted(ausentes))
            raise RuntimeError(f"Checkpoint incompleto; campos ausentes: {nomes}.")

        arquitetura = bruto["arquitetura"]
        if not isinstance(arquitetura, dict):
            raise RuntimeError(
                "Checkpoint inválido: arquitetura ausente ou malformada."
            )
        nome = arquitetura.get("nome")
        encoder = arquitetura.get("encoder")
        if not isinstance(nome, str) or not nome.strip():
            raise RuntimeError("Checkpoint inválido: nome da arquitetura ausente.")
        if nome != "Unet":
            raise RuntimeError("Checkpoint incompatível: a arquitetura deve ser Unet.")
        if not isinstance(encoder, str) or not encoder.strip():
            raise RuntimeError("Checkpoint inválido: encoder ausente.")
        if arquitetura.get("classes") != _NUMERO_CLASSES:
            raise RuntimeError("Checkpoint incompatível: são exigidas três classes.")

        entrada = bruto["entrada"]
        if entrada != {"largura": _LARGURA_ENTRADA, "altura": _ALTURA_ENTRADA}:
            raise RuntimeError("Checkpoint incompatível: resolução esperada é 768×576.")

        normalizacao = bruto["normalizacao"]
        if not isinstance(normalizacao, dict) or not _normalizacao_compativel(
            normalizacao
        ):
            raise RuntimeError(
                "Checkpoint incompatível: normalização ImageNet esperada."
            )
        classes_checkpoint = bruto["classes"]
        if (
            not isinstance(classes_checkpoint, (list, tuple))
            or tuple(classes_checkpoint) != _CLASSES
        ):
            raise RuntimeError("Checkpoint incompatível: nomes ou ordem das classes.")
        if not isinstance(bruto["state_dict"], dict):
            raise RuntimeError("Checkpoint inválido: state_dict ausente ou malformado.")

        return bruto

    def _aquecimento(self) -> None:
        """Executa uma passagem completa antes de aceitar requisições."""
        tensor = self._torch.zeros(
            (1, 3, _ALTURA_ENTRADA, _LARGURA_ENTRADA),
            dtype=self._torch.float32,
            device="cpu",
        )
        try:
            with self._torch.inference_mode():
                saida = self._modelo(tensor)
            self._validar_saida(saida)
        except Exception as erro:
            raise RuntimeError("O modelo falhou no passe de aquecimento.") from erro

    def _validar_saida(self, saida: Any) -> None:
        """Exige logits finitos nas três classes e na resolução de entrada."""
        if not isinstance(saida, self._torch.Tensor):
            raise RuntimeError("O modelo deve retornar um tensor de logits.")
        forma_esperada = (1, _NUMERO_CLASSES, _ALTURA_ENTRADA, _LARGURA_ENTRADA)
        if tuple(saida.shape) != forma_esperada:
            raise RuntimeError("O modelo retornou logits com dimensões incompatíveis.")
        if not bool(self._torch.isfinite(saida).all().item()):
            raise RuntimeError("O modelo retornou logits não finitos.")

    def inferir(self, imagem: bytes) -> ResultadoInferencia:
        """Executa a segmentação e retorna percentual, status e PNG sobreposto.

        Args:
            imagem: Conteúdo binário da imagem original.

        Returns:
            Resultado de cobertura e máscara na resolução da imagem recebida.

        Raises:
            FalhaInferencia: Se a imagem for inválida ou exceder o teto de pixels.
            PlacaNaoDetectada: Se a saída não localizar uma área de placa suficiente.
        """
        try:
            with self._lock:
                original = self._decodificar_imagem(imagem)
                entrada = self._preprocessar(original)
                with self._torch.inference_mode():
                    saida = self._modelo(entrada)
                self._validar_saida(saida)
                rotulos = saida.argmax(dim=1)[0].to(dtype=self._torch.uint8)
                pixels_cobertos = int((rotulos == 2).sum().item())
                pixels_limpos = int((rotulos == 1).sum().item())
                area_placa = pixels_cobertos + pixels_limpos
                area_total = _LARGURA_ENTRADA * _ALTURA_ENTRADA
                if area_placa == 0 or area_placa < area_total * _AREA_MINIMA_PLACA:
                    raise PlacaNaoDetectada("A placa não foi localizada na imagem.")

                percentual = (
                    Decimal(pixels_cobertos) * Decimal("100") / Decimal(area_placa)
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                mascara = self._criar_mascara(original, rotulos)

            return ResultadoInferencia(
                percentual_coberto=percentual,
                status=derivar_status(
                    percentual,
                    self._limiar_atencao,
                    self._limiar_trocar,
                ),
                modelo_versao=self._modelo_versao,
                mascara=mascara,
            )
        except (FalhaInferencia, PlacaNaoDetectada):
            raise
        except Exception as erro:
            logger.exception("Falha inesperada durante a inferência.")
            raise FalhaInferencia(_MENSAGEM_IMAGEM_INVALIDA) from erro

    @staticmethod
    def _decodificar_imagem(imagem: bytes) -> Image.Image:
        """Abre a imagem sem alterar a orientação gravada pelos pixels da câmera."""
        try:
            with Image.open(BytesIO(imagem)) as arquivo:
                largura, altura = arquivo.size
                if largura <= 0 or altura <= 0:
                    raise FalhaInferencia(_MENSAGEM_IMAGEM_INVALIDA)
                if largura * altura > LIMITE_PIXELS_IMAGEM:
                    raise FalhaInferencia(_MENSAGEM_IMAGEM_INVALIDA)
                arquivo.load()
                original = arquivo.convert("RGB")
                if "exif" in arquivo.info:
                    original.info["exif"] = arquivo.info["exif"]
                return original
        except (Image.DecompressionBombError, OSError, ValueError):
            raise FalhaInferencia(_MENSAGEM_IMAGEM_INVALIDA) from None

    def _preprocessar(self, original: Image.Image) -> Any:
        """Redimensiona e normaliza a imagem para o tensor usado no treino."""
        redimensionada = original.resize(
            (_LARGURA_ENTRADA, _ALTURA_ENTRADA),
            resample=Image.Resampling.BILINEAR,
        )
        buffer = bytearray(redimensionada.tobytes())
        tensor = self._torch.frombuffer(buffer, dtype=self._torch.uint8)
        tensor = tensor.reshape(_ALTURA_ENTRADA, _LARGURA_ENTRADA, 3)
        tensor = tensor.permute(2, 0, 1).unsqueeze(0).to(dtype=self._torch.float32)
        tensor = tensor.div_(255.0)
        return (tensor - self._media) / self._desvio

    @staticmethod
    def _criar_mascara(original: Image.Image, rotulos: Any) -> bytes:
        """Projeta os rótulos sobre a imagem original com vizinho mais próximo."""
        rotulos_bytes = bytes(rotulos.contiguous().reshape(-1).tolist())
        mapa = Image.frombytes(
            "L",
            (_LARGURA_ENTRADA, _ALTURA_ENTRADA),
            rotulos_bytes,
        )
        mapa_original = mapa.resize(original.size, resample=Image.Resampling.NEAREST)
        alfa = mapa_original.point(
            lambda rotulo: _OPACIDADE_MASCARA if rotulo == 2 else 0
        )
        sobreposicao = Image.new("RGBA", original.size, (255, 0, 255, 0))
        sobreposicao.putalpha(alfa)
        resultado = Image.alpha_composite(original.convert("RGBA"), sobreposicao)
        if "exif" in original.info:
            resultado.info["exif"] = original.info["exif"]
        resultado = ImageOps.exif_transpose(resultado)
        buffer = BytesIO()
        resultado.save(buffer, format="PNG", optimize=False)
        return buffer.getvalue()


def _normalizacao_compativel(normalizacao: dict[str, Any]) -> bool:
    """Compara os metadados do checkpoint com os valores ImageNet do treino."""
    media = normalizacao.get("media")
    desvio = normalizacao.get("desvio")
    if not isinstance(media, (list, tuple)) or not isinstance(desvio, (list, tuple)):
        return False
    if len(media) != 3 or len(desvio) != 3:
        return False
    try:
        return all(
            math.isclose(float(valor), esperado, rel_tol=0.0, abs_tol=1e-7)
            for valor, esperado in zip(media, _MEDIA_IMAGENET, strict=True)
        ) and all(
            math.isclose(float(valor), esperado, rel_tol=0.0, abs_tol=1e-7)
            for valor, esperado in zip(desvio, _DESVIO_IMAGENET, strict=True)
        )
    except (TypeError, ValueError):
        return False
