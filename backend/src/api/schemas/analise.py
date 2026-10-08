"""Schema da representação pública de uma análise persistida."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_serializer

from src.entities import StatusAnalise


class AnaliseSaida(BaseModel):
    """Campos devolvidos pelo cadastro e pela consulta individual de análise."""

    id: UUID
    refil_id: UUID
    armadilha_id: UUID
    analisado_em: datetime
    percentual_coberto: Decimal
    status: StatusAnalise
    modelo_versao: str
    imagem_url: str
    mascara_url: str

    @field_serializer("percentual_coberto", when_used="json")
    def _serializar_percentual(self, valor: Decimal) -> float:
        """Emite o percentual como número JSON sem perder a precisão armazenada."""
        return float(valor)

    @field_serializer("analisado_em", when_used="json")
    def _serializar_instante_utc(self, valor: datetime) -> str:
        """Normaliza o instante ao sufixo UTC esperado pelos clientes da API."""
        if valor.tzinfo is None or valor.utcoffset() is None:
            raise ValueError("O instante da análise deve incluir fuso horário.")
        return valor.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
