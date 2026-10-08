"""Define os valores e as falhas compartilhados pelo pipeline de inferência."""

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Protocol, runtime_checkable

from src.entities.status import StatusAnalise

_DUAS_CASAS = Decimal("0.01")
_IDENTIFICADOR_PRE_RELEASE = r"(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)"
_FORMATO_SEMVER = re.compile(
    rf"v?(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
    rf"(?:-{_IDENTIFICADOR_PRE_RELEASE}(?:\.{_IDENTIFICADOR_PRE_RELEASE})*)?"
)
_FORMATO_HASH_MODELO = re.compile(r"[0-9A-Fa-f]{8}")


def validar_versao_semver(versao: str) -> None:
    """Valida a versão SemVer recebida antes de iniciar a inferência.

    Args:
        versao: Versão com três componentes numéricos e pré-release opcional.

    Raises:
        ValueError: Se o texto não seguir o formato SemVer aceito.
    """
    if not isinstance(versao, str) or _FORMATO_SEMVER.fullmatch(versao) is None:
        raise ValueError("A versão do modelo deve seguir SemVer.")


class ErroDeInferencia(Exception):
    """Classe base para falhas ocorridas durante a inferência."""


class PlacaNaoDetectada(ErroDeInferencia):
    """Indica que a placa adesiva não pôde ser localizada na imagem."""


class FalhaInferencia(ErroDeInferencia):
    """Indica que a imagem não pôde ser processada pela inferência."""


@dataclass(frozen=True, slots=True)
class ResultadoInferencia:
    """Resultado completo produzido por uma implementação de inferência.

    Args:
        percentual_coberto: Percentual entre zero e cem, arredondado a centésimos.
        status: Classificação associada ao percentual.
        modelo_versao: Versão semântica do modelo e hash de oito caracteres.
        mascara: Conteúdo da máscara no formato PNG.

    Raises:
        TypeError: Se algum campo tiver um tipo incompatível com o contrato.
        ValueError: Se percentual ou versão estiverem fora do formato aceito.
    """

    percentual_coberto: Decimal
    status: StatusAnalise
    modelo_versao: str
    mascara: bytes

    def __post_init__(self) -> None:
        """Valida os campos e normaliza o percentual para duas casas decimais."""
        if not isinstance(self.percentual_coberto, Decimal):
            raise TypeError("percentual_coberto deve ser Decimal.")
        if not self.percentual_coberto.is_finite():
            raise ValueError("percentual_coberto deve ser finito.")
        if not Decimal("0") <= self.percentual_coberto <= Decimal("100"):
            raise ValueError("percentual_coberto deve estar entre zero e cem.")
        try:
            percentual = self.percentual_coberto.quantize(
                _DUAS_CASAS,
                rounding=ROUND_HALF_UP,
            )
        except InvalidOperation as erro:
            raise ValueError("percentual_coberto não pode ser arredondado.") from erro
        object.__setattr__(self, "percentual_coberto", percentual)

        if not isinstance(self.status, StatusAnalise):
            raise TypeError("status deve ser um StatusAnalise.")
        if not isinstance(self.modelo_versao, str):
            raise TypeError("modelo_versao deve ser str.")
        versao, separador, hash_modelo = self.modelo_versao.rpartition("+")
        if not separador or _FORMATO_HASH_MODELO.fullmatch(hash_modelo) is None:
            raise ValueError("modelo_versao deve usar semver e hash de oito dígitos.")
        validar_versao_semver(versao)
        if not isinstance(self.mascara, bytes):
            raise TypeError("mascara deve ser bytes no formato PNG.")


@runtime_checkable
class Inferidor(Protocol):
    """Interface implementada por qualquer componente que analise uma imagem."""

    def inferir(self, imagem: bytes) -> ResultadoInferencia:
        """Analisa bytes de uma imagem e devolve o resultado completo.

        Args:
            imagem: Conteúdo binário da imagem original.

        Returns:
            Percentual coberto, classificação, versão e máscara PNG.

        Raises:
            ErroDeInferencia: Se a placa não for localizada ou a imagem falhar.
        """
