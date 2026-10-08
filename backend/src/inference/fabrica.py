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
    return InferidorStub(
        modelo_versao=settings.model_version,
        limiar_atencao=Decimal(settings.limiar_atencao),
        limiar_trocar=Decimal(settings.limiar_trocar),
    )
