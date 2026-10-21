"""Entidades persistidas no banco de dados."""

from src.entities.analise import Analise
from src.entities.armadilha import Armadilha
from src.entities.base import Base
from src.entities.refil import Refil
from src.entities.sessao import Sessao
from src.entities.status import StatusAnalise
from src.entities.tentativa_login import TentativaLogin
from src.entities.usuario import Usuario

__all__ = [
    "Analise",
    "Armadilha",
    "Base",
    "Refil",
    "Sessao",
    "StatusAnalise",
    "TentativaLogin",
    "Usuario",
]
