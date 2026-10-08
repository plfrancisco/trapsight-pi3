"""Contrato e implementações de inferência de imagens."""

from src.inference.contrato import (
    ErroDeInferencia,
    FalhaInferencia,
    Inferidor,
    PlacaNaoDetectada,
    ResultadoInferencia,
)
from src.inference.fabrica import criar_inferidor
from src.inference.status import derivar_status

__all__ = [
    "ErroDeInferencia",
    "FalhaInferencia",
    "Inferidor",
    "PlacaNaoDetectada",
    "ResultadoInferencia",
    "criar_inferidor",
    "derivar_status",
]
