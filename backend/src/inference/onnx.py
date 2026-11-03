"""Inferência de segmentação com ONNX Runtime em CPU."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from decimal import ROUND_HALF_UP, Decimal
from io import BytesIO
from pathlib import Path
from threading import Lock

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageOps

from src.inference.contrato import (
    FalhaInferencia,
    PlacaNaoDetectada,
    ResultadoInferencia,
    validar_versao_semver,
)
from src.inference.modelo import InferidorModelo
from src.inference.status import derivar_status

_FORMA = (1, 3, 576, 768)
_MEDIA = np.array((0.485, 0.456, 0.406), dtype=np.float32).reshape(1, 3, 1, 1)
_DESVIO = np.array((0.229, 0.224, 0.225), dtype=np.float32).reshape(1, 3, 1, 1)
_LOG = logging.getLogger(__name__)


class InferidorOnnx:
    """Carrega e valida o modelo ONNX uma vez antes de atender requisições."""

    def __init__(
        self,
        caminho_pesos: str | Path,
        modelo_versao: str,
        limiar_atencao: Decimal,
        limiar_trocar: Decimal,
        threads: int = 1,
    ):
        """Valida metadados, integridade, dimensões e saída do modelo."""
        validar_versao_semver(modelo_versao)
        if threads < 1:
            raise ValueError("O número de threads de inferência deve ser positivo.")
        caminho = Path(caminho_pesos)
        try:
            metadados = json.loads(
                caminho.with_suffix(".json").read_text(encoding="utf-8-sig")
            )
            with caminho.open("rb") as arquivo:
                resumo = hashlib.file_digest(arquivo, "sha256").hexdigest()
        except (OSError, ValueError) as erro:
            raise RuntimeError(
                "Modelo ONNX ou metadados ausentes ou ilegíveis."
            ) from erro
        if not isinstance(metadados, dict):
            raise RuntimeError("Metadados ONNX devem formar um objeto JSON.")
        if resumo != metadados.get("onnx_sha256"):
            raise RuntimeError("SHA-256 do modelo ONNX não corresponde aos metadados.")
        if (
            metadados.get("entrada") != {"largura": 768, "altura": 576}
            or metadados.get("classes") != ["fundo", "placa_limpa", "placa_coberta"]
            or metadados.get("normalizacao")
            != {"media": [0.485, 0.456, 0.406], "desvio": [0.229, 0.224, 0.225]}
        ):
            raise RuntimeError("Metadados do modelo ONNX incompatíveis.")
        checkpoint_sha = metadados.get("checkpoint_sha256")
        if not isinstance(checkpoint_sha, str) or not re.fullmatch(
            r"[0-9a-f]{64}", checkpoint_sha
        ):
            raise RuntimeError("SHA-256 do checkpoint ausente ou inválido.")
        self._versao = metadados.get("versao")
        if self._versao != f"{modelo_versao}+{checkpoint_sha[:8]}":
            raise RuntimeError("Versão configurada diverge dos metadados ONNX.")
        self._atencao, self._trocar = limiar_atencao, limiar_trocar
        self._lock = Lock()
        try:
            opcoes = ort.SessionOptions()
            opcoes.intra_op_num_threads = threads
            self._sessao = ort.InferenceSession(
                str(caminho), sess_options=opcoes, providers=["CPUExecutionProvider"]
            )
            entradas, saidas = self._sessao.get_inputs(), self._sessao.get_outputs()
            if (
                len(entradas) != 1
                or len(saidas) != 1
                or tuple(entradas[0].shape) != _FORMA
                or tuple(saidas[0].shape) != _FORMA
                or entradas[0].type != "tensor(float)"
                or saidas[0].type != "tensor(float)"
            ):
                raise RuntimeError("Dimensões ou tipos do modelo ONNX incompatíveis.")
            self._entrada = entradas[0].name
            self._executar(np.zeros(_FORMA, dtype=np.float32))
        except Exception as erro:
            raise RuntimeError(f"Falha ao inicializar o modelo ONNX: {erro}") from erro

    def _executar(self, entrada: np.ndarray) -> np.ndarray:
        saida = self._sessao.run(None, {self._entrada: entrada})[0]
        if saida.shape != _FORMA or not np.isfinite(saida).all():
            raise RuntimeError("Saída ONNX tem forma inválida ou valores não finitos.")
        return saida

    def inferir(self, imagem: bytes) -> ResultadoInferencia:
        """Retorna cobertura, classificação e imagem PNG com máscara sobreposta."""
        try:
            with self._lock:
                original = InferidorModelo._decodificar_imagem(imagem)
                redimensionada = original.resize((768, 576), Image.Resampling.BILINEAR)
                entrada = np.asarray(redimensionada, dtype=np.float32).transpose(
                    2, 0, 1
                )[None] / np.float32(255)
                rotulos = (
                    self._executar((entrada - _MEDIA) / _DESVIO)
                    .argmax(axis=1)[0]
                    .astype(np.uint8)
                )
                cobertos = int(np.count_nonzero(rotulos == 2))
                area = cobertos + int(np.count_nonzero(rotulos == 1))
                if area < 768 * 576 * 0.05:
                    raise PlacaNaoDetectada("A placa não foi localizada na imagem.")
                percentual = (Decimal(cobertos) * 100 / Decimal(area)).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                mapa = Image.frombytes("L", (768, 576), rotulos.tobytes()).resize(
                    original.size, Image.Resampling.NEAREST
                )
                overlay = Image.new("RGBA", original.size, (255, 0, 255, 0))
                overlay.putalpha(mapa.point(lambda x: 102 if x == 2 else 0))
                resultado = Image.alpha_composite(original.convert("RGBA"), overlay)
                if "exif" in original.info:
                    resultado.info["exif"] = original.info["exif"]
                resultado = ImageOps.exif_transpose(resultado)
                buffer = BytesIO()
                resultado.save(buffer, format="PNG", optimize=False)
            return ResultadoInferencia(
                percentual,
                derivar_status(percentual, self._atencao, self._trocar),
                self._versao,
                buffer.getvalue(),
            )
        except (FalhaInferencia, PlacaNaoDetectada):
            raise
        except Exception as erro:
            _LOG.exception("Falha inesperada durante a inferência ONNX.")
            raise FalhaInferencia("A imagem não pôde ser processada.") from erro
