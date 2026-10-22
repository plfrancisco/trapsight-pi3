"""Construção do modelo, congelamento do encoder e formato do checkpoint."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import segmentation_models_pytorch as smp
import torch
from torch import nn

from training.treino.aumentos import DESVIO_IMAGENET, MEDIA_IMAGENET
from training.treino.configuracao import CLASSES, Configuracao


def criar_modelo(configuracao: Configuracao) -> nn.Module:
    """U-Net de três classes com o encoder pedido (ImageNet por padrão)."""
    arquitetura = getattr(smp, configuracao.arquitetura, None)
    if arquitetura is None:
        raise ValueError(f"Arquitetura desconhecida: {configuracao.arquitetura}.")
    return arquitetura(
        encoder_name=configuracao.encoder,
        encoder_weights="imagenet" if configuracao.encoder_pretreinado else None,
        in_channels=3,
        classes=len(CLASSES),
    )


def congelar_encoder(modelo: nn.Module, congelar: bool) -> None:
    """Liga ou desliga o gradiente dos pesos do encoder."""
    for parametro in modelo.encoder.parameters():
        parametro.requires_grad = not congelar


def colocar_em_treino(modelo: nn.Module, bn_encoder_congelado: bool) -> None:
    """Modo de treino; mantém as estatísticas de BatchNorm do encoder fixas.

    Com lote pequeno por passo, as estatísticas do lote são ruidosas; manter as
    do ImageNet no encoder é mais estável (treino_spec.md, seção 2.3).
    """
    modelo.train()
    if bn_encoder_congelado:
        for modulo in modelo.encoder.modules():
            if isinstance(modulo, nn.modules.batchnorm._BatchNorm):
                modulo.eval()


def grupos_de_parametros(
    modelo: nn.Module, configuracao: Configuracao
) -> list[dict[str, Any]]:
    """Taxa menor no encoder pré-treinado e maior no decoder inicializado ao acaso."""
    return [
        {
            "params": list(modelo.encoder.parameters()),
            "lr": configuracao.lr_encoder,
            "base_lr": configuracao.lr_encoder,
        },
        {
            "params": [
                *modelo.decoder.parameters(),
                *modelo.segmentation_head.parameters(),
            ],
            "lr": configuracao.lr_decoder,
            "base_lr": configuracao.lr_decoder,
        },
    ]


def montar_checkpoint(modelo: nn.Module, configuracao: Configuracao) -> dict[str, Any]:
    """Checkpoint que a inferência lê sem depender do código de treino."""
    return {
        "state_dict": {k: v.detach().cpu() for k, v in modelo.state_dict().items()},
        "arquitetura": {
            "nome": configuracao.arquitetura,
            "encoder": configuracao.encoder,
            "classes": len(CLASSES),
        },
        "entrada": {"largura": configuracao.largura, "altura": configuracao.altura},
        "normalizacao": {
            "media": list(MEDIA_IMAGENET),
            "desvio": list(DESVIO_IMAGENET),
        },
        "classes": list(CLASSES),
    }


def gravar_checkpoint(
    modelo: nn.Module, configuracao: Configuracao, caminho: Path
) -> str:
    """Grava o checkpoint e devolve o `modelo_versao` (semver + 8 hex do SHA-256)."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    torch.save(montar_checkpoint(modelo, configuracao), caminho)
    return f"{configuracao.versao_modelo}+{hash_curto(caminho)}"


def hash_curto(caminho: Path) -> str:
    """Oito primeiros caracteres do SHA-256 do arquivo de pesos."""
    resumo = hashlib.sha256()
    with Path(caminho).open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            resumo.update(bloco)
    return resumo.hexdigest()[:8]


def carregar_checkpoint(
    caminho: Path, dispositivo: str = "cpu"
) -> tuple[nn.Module, dict[str, Any]]:
    """Reconstrói o modelo a partir de um checkpoint gravado por `gravar_checkpoint`."""
    bruto = torch.load(Path(caminho), map_location=dispositivo, weights_only=True)
    arquitetura = bruto["arquitetura"]
    modelo = getattr(smp, arquitetura["nome"])(
        encoder_name=arquitetura["encoder"],
        encoder_weights=None,
        in_channels=3,
        classes=arquitetura["classes"],
    )
    modelo.load_state_dict(bruto["state_dict"])
    return modelo.to(dispositivo), bruto
