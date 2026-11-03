"""Criação de uma implementação compatível com o contrato de inferência."""

from decimal import Decimal

from src.config.settings import Settings
from src.inference.contrato import Inferidor
from src.inference.stub import InferidorStub


def criar_inferidor(settings: Settings) -> Inferidor:
    """Constrói o inferidor atual a partir dos limiares e da versão configurados.

    Args:
        settings: Configuração validada carregada pelo backend.

    Returns:
        Implementação do protocolo de inferência.
    """
    limiar_atencao = Decimal(settings.limiar_atencao)
    limiar_trocar = Decimal(settings.limiar_trocar)
    if settings.inference_mode == "stub":
        return InferidorStub(
            modelo_versao=settings.model_version,
            limiar_atencao=limiar_atencao,
            limiar_trocar=limiar_trocar,
        )

    if settings.inference_mode == "onnx":
        from pathlib import Path

        from src.inference.onnx import InferidorOnnx

        caminho = settings.model_weights_path.strip() or str(
            Path(__file__).resolve().parents[2] / "models" / "modelo.onnx"
        )
        return InferidorOnnx(
            caminho_pesos=caminho,
            modelo_versao=settings.model_version,
            limiar_atencao=limiar_atencao,
            limiar_trocar=limiar_trocar,
            threads=settings.inference_threads,
        )

    from src.inference.modelo import InferidorModelo

    return InferidorModelo(
        caminho_pesos=settings.model_weights_path,
        modelo_versao=settings.model_version,
        limiar_atencao=limiar_atencao,
        limiar_trocar=limiar_trocar,
        threads=settings.inference_threads,
    )
