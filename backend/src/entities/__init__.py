"""Entidades persistidas no banco de dados."""

from src.entities.analise import Analise
from src.entities.armadilha import Armadilha
from src.entities.base import Base
from src.entities.refil import Refil
from src.entities.status import StatusAnalise

__all__ = ["Analise", "Armadilha", "Base", "Refil", "StatusAnalise"]
