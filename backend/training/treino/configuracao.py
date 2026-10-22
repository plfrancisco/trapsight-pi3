"""Configuração versionada do treino; nenhum hiperparâmetro fica no loop."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Any

CLASSES = ("fundo", "placa_limpa", "placa_coberta")
INDICE_PLACA_LIMPA = 1
INDICE_PLACA_COBERTA = 2
LIMIAR_ATENCAO = 10.0
LIMIAR_TROCAR = 20.0
CONFIGURACAO_PADRAO = Path(__file__).with_name("configuracao_padrao.json")


@dataclass(frozen=True)
class Configuracao:
    """Hiperparâmetros e caminhos de uma execução de treino."""

    nome: str = "execucao"
    dataset: str = ""
    saida: str = ""
    versao_modelo: str = "v0.1.0"
    semente_global: int = 20261021
    largura: int = 768
    altura: int = 576
    arquitetura: str = "Unet"
    encoder: str = "resnet34"
    encoder_pretreinado: bool = True
    bn_encoder_congelado: bool = True
    congelar_encoder_epocas: int = 3
    batch_por_passo: int | str = "auto"
    batch_efetivo: int = 8
    epocas_maximas: int = 60
    aquecimento_epocas: int = 2
    lr_decoder: float = 3e-4
    lr_encoder: float = 1e-4
    lr_minimo: float = 1e-6
    weight_decay: float = 1e-4
    corte_gradiente: float = 1.0
    paciencia: int = 10
    melhora_minima_pp: float = 0.05
    peso_expoente: float = 0.5
    peso_teto: float = 10.0
    lambda_area: float = 0.0
    precisao_mista: bool = True
    num_workers: int = 2
    limite_amostras_treino: int | None = None
    limite_amostras_validacao: int | None = None
    descricao: str = ""

    def validar(self) -> None:
        """Rejeita combinações que quebrariam o treino ou a especificação."""
        if self.largura % 32 or self.altura % 32:
            raise ValueError("Largura e altura precisam ser múltiplas de 32.")
        if self.batch_efetivo < 1:
            raise ValueError("O lote efetivo precisa ser positivo.")
        if self.batch_por_passo != "auto" and (
            not isinstance(self.batch_por_passo, int) or self.batch_por_passo < 1
        ):
            raise ValueError("batch_por_passo deve ser 'auto' ou um inteiro positivo.")
        if self.epocas_maximas < 1:
            raise ValueError("epocas_maximas precisa ser positiva.")
        if self.congelar_encoder_epocas < 0 or self.aquecimento_epocas < 0:
            raise ValueError(
                "Épocas de congelamento e aquecimento não podem ser negativas."
            )
        if not 0 < self.peso_expoente <= 2 or self.peso_teto < 1:
            raise ValueError("Parâmetros dos pesos de classe fora da faixa válida.")
        if self.lambda_area < 0:
            raise ValueError("lambda_area não pode ser negativo.")
        for nome in ("limite_amostras_treino", "limite_amostras_validacao"):
            valor = getattr(self, nome)
            if valor is not None and valor < 1:
                raise ValueError(f"{nome} precisa ser positivo quando informado.")

    def como_dicionario(self) -> dict[str, Any]:
        """Representação serializável, gravada em cada execução."""
        return asdict(self)

    def com(self, **alteracoes: Any) -> Configuracao:
        """Cópia com campos substituídos, já validada."""
        nova = replace(self, **{k: v for k, v in alteracoes.items() if v is not None})
        nova.validar()
        return nova


def carregar_configuracao(caminho: Path = CONFIGURACAO_PADRAO) -> Configuracao:
    """Lê um arquivo JSON de configuração, recusando campos desconhecidos."""
    try:
        bruto = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except FileNotFoundError as erro:
        raise ValueError(f"Configuração ausente: {caminho}.") from erro
    except json.JSONDecodeError as erro:
        raise ValueError("A configuração precisa conter JSON válido.") from erro
    if not isinstance(bruto, dict):
        raise ValueError("A configuração precisa ser um objeto JSON.")
    conhecidos = {campo.name for campo in fields(Configuracao)}
    desconhecidos = sorted(set(bruto) - conhecidos)
    if desconhecidos:
        raise ValueError(f"Campos desconhecidos na configuração: {desconhecidos}.")
    configuracao = Configuracao(**bruto)
    configuracao.validar()
    return configuracao
