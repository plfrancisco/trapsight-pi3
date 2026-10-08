"""Classificação do percentual de cobertura pelos limiares configurados."""

from decimal import Decimal

from src.entities.status import StatusAnalise


def derivar_status(
    percentual: Decimal,
    limiar_atencao: Decimal,
    limiar_trocar: Decimal,
) -> StatusAnalise:
    """Classifica o percentual sem perder precisão decimal.

    Args:
        percentual: Cobertura medida entre zero e cem.
        limiar_atencao: Início inclusivo do estado de atenção.
        limiar_trocar: Limite inclusivo superior do estado de atenção.

    Returns:
        Estado persistido correspondente aos limiares.

    Raises:
        TypeError: Se os valores não forem Decimal.
        ValueError: Se os valores ou limiares estiverem fora da faixa válida.
    """
    valores = (percentual, limiar_atencao, limiar_trocar)
    if any(not isinstance(valor, Decimal) for valor in valores):
        raise TypeError("Percentual e limiares devem ser Decimal.")
    if any(not valor.is_finite() for valor in valores):
        raise ValueError("Percentual e limiares devem ser finitos.")
    if not Decimal("0") <= percentual <= Decimal("100"):
        raise ValueError("percentual deve estar entre zero e cem.")
    if not Decimal("0") < limiar_atencao < limiar_trocar <= Decimal("100"):
        raise ValueError("Os limiares devem estar em ordem entre zero e cem.")

    if percentual < limiar_atencao:
        return StatusAnalise.OK
    if percentual <= limiar_trocar:
        return StatusAnalise.ATENCAO
    return StatusAnalise.TROCAR
