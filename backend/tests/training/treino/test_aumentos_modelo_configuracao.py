"""Augmentation, modelo, checkpoint e configuração do treino."""

from __future__ import annotations

import json
import re

import numpy as np
import pytest
import torch
from torch import nn

from training.treino.aumentos import transformacao_avaliacao, transformacao_treino
from training.treino.configuracao import (
    CONFIGURACAO_PADRAO,
    Configuracao,
    carregar_configuracao,
)
from training.treino.modelo import (
    carregar_checkpoint,
    colocar_em_treino,
    congelar_encoder,
    criar_modelo,
    gravar_checkpoint,
    grupos_de_parametros,
)

PROIBIDAS = {
    "CoarseDropout",
    "GridDropout",
    "RandomCrop",
    "RandomResizedCrop",
    "CropNonEmptyMaskIfExists",
    "MixUp",
    "CutMix",
    "Cutout",
}


def _par(tamanho: int = 96):
    imagem = np.random.default_rng(0).integers(
        0, 255, (tamanho, tamanho, 3), dtype=np.uint8
    )
    mascara = np.zeros((tamanho, tamanho), dtype=np.uint8)
    mascara[10:80, 10:80] = 1
    mascara[20:50, 20:50] = 2
    return imagem, mascara


def test_pipeline_de_treino_nao_tem_transformacoes_que_alteram_a_razao_entre_areas():
    nomes = {type(t).__name__ for t in transformacao_treino().transforms}

    assert not nomes & PROIBIDAS


def test_augmentation_preserva_formato_e_so_gera_as_tres_classes():
    imagem, mascara = _par()
    transformacao = transformacao_treino()

    for semente in range(20):
        transformacao.set_random_seed(semente)
        saida = transformacao(image=imagem, mask=mascara)

        assert saida["image"].shape == (3, 96, 96)
        assert saida["image"].dtype == torch.float32
        assert saida["mask"].shape == (96, 96)
        assert set(np.unique(saida["mask"].numpy())) <= {0, 1, 2}


def test_mesma_semente_repete_a_augmentation_e_outra_semente_muda():
    imagem, mascara = _par()
    transformacao = transformacao_treino()

    transformacao.set_random_seed(11)
    primeira = transformacao(image=imagem, mask=mascara)
    transformacao.set_random_seed(11)
    repetida = transformacao(image=imagem, mask=mascara)
    transformacao.set_random_seed(12)
    outra = transformacao(image=imagem, mask=mascara)

    assert torch.equal(primeira["image"], repetida["image"])
    assert torch.equal(primeira["mask"], repetida["mask"])
    assert not torch.equal(primeira["image"], outra["image"])


def test_avaliacao_so_normaliza_com_os_valores_do_imagenet():
    imagem = np.zeros((32, 32, 3), dtype=np.uint8)
    mascara = np.zeros((32, 32), dtype=np.uint8)

    saida = transformacao_avaliacao()(image=imagem, mask=mascara)

    esperado = torch.tensor([-0.485 / 0.229, -0.456 / 0.224, -0.406 / 0.225])
    assert torch.allclose(saida["image"][:, 0, 0], esperado, atol=1e-5)


def test_modelo_tem_tres_canais_de_saida_na_resolucao_de_entrada():
    modelo = criar_modelo(Configuracao(encoder_pretreinado=False)).eval()

    with torch.no_grad():
        saida = modelo(torch.zeros(2, 3, 64, 64))

    assert saida.shape == (2, 3, 64, 64)


def test_congelar_encoder_desliga_o_gradiente_apenas_dele():
    modelo = criar_modelo(Configuracao(encoder_pretreinado=False))

    congelar_encoder(modelo, True)
    assert not any(p.requires_grad for p in modelo.encoder.parameters())
    assert all(p.requires_grad for p in modelo.decoder.parameters())

    congelar_encoder(modelo, False)
    assert all(p.requires_grad for p in modelo.encoder.parameters())


def test_batchnorm_do_encoder_fica_em_avaliacao_mas_o_do_decoder_treina():
    modelo = criar_modelo(Configuracao(encoder_pretreinado=False))

    colocar_em_treino(modelo, bn_encoder_congelado=True)

    bn_encoder = [m for m in modelo.encoder.modules() if isinstance(m, nn.BatchNorm2d)]
    bn_decoder = [m for m in modelo.decoder.modules() if isinstance(m, nn.BatchNorm2d)]
    assert bn_encoder and not any(m.training for m in bn_encoder)
    assert bn_decoder and all(m.training for m in bn_decoder)

    colocar_em_treino(modelo, bn_encoder_congelado=False)
    assert all(m.training for m in bn_encoder)


def test_taxas_de_aprendizado_diferem_entre_encoder_e_decoder():
    configuracao = Configuracao(
        encoder_pretreinado=False, lr_encoder=1e-4, lr_decoder=3e-4
    )
    modelo = criar_modelo(configuracao)

    grupos = grupos_de_parametros(modelo, configuracao)

    assert [g["lr"] for g in grupos] == [1e-4, 3e-4]
    cobertos = {id(p) for g in grupos for p in g["params"]}
    assert cobertos == {id(p) for p in modelo.parameters()}


def test_checkpoint_e_recarregado_sem_o_codigo_de_treino(tmp_path):
    configuracao = Configuracao(encoder_pretreinado=False, versao_modelo="v0.3.1")
    modelo = criar_modelo(configuracao).eval()

    versao = gravar_checkpoint(modelo, configuracao, tmp_path / "melhor.pt")
    recarregado, bruto = carregar_checkpoint(tmp_path / "melhor.pt")
    recarregado.eval()

    assert re.fullmatch(r"v0\.3\.1\+[0-9a-f]{8}", versao)
    assert bruto["arquitetura"] == {"nome": "Unet", "encoder": "resnet34", "classes": 3}
    assert bruto["entrada"] == {"largura": 768, "altura": 576}
    assert bruto["classes"] == ["fundo", "placa_limpa", "placa_coberta"]
    entrada = torch.randn(1, 3, 64, 64)
    with torch.no_grad():
        assert torch.allclose(modelo(entrada), recarregado(entrada), atol=1e-6)


def test_configuracao_padrao_carrega_e_segue_a_especificacao():
    configuracao = carregar_configuracao(CONFIGURACAO_PADRAO)

    assert (configuracao.largura, configuracao.altura) == (768, 576)
    assert configuracao.encoder == "resnet34" and configuracao.encoder_pretreinado
    assert configuracao.batch_efetivo == 8 and configuracao.congelar_encoder_epocas == 3
    assert configuracao.lambda_area == 0.0 and configuracao.paciencia == 10


def test_configuracao_recusa_campo_desconhecido(tmp_path):
    arquivo = tmp_path / "config.json"
    arquivo.write_text(json.dumps({"epocas_maximas": 3, "campo_inventado": 1}))

    with pytest.raises(ValueError, match="desconhecidos"):
        carregar_configuracao(arquivo)


@pytest.mark.parametrize(
    "alteracao",
    [
        {"largura": 770},
        {"batch_efetivo": 0},
        {"batch_por_passo": 0},
        {"lambda_area": -1.0},
    ],
)
def test_configuracao_invalida_e_recusada(alteracao):
    with pytest.raises(ValueError):
        Configuracao().com(**alteracao)
