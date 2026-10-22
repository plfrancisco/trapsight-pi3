"""Perda, métricas e seleção do melhor ponto."""

from __future__ import annotations

import pytest
import torch

from training.treino.metricas import AcumuladorMetricas, derivar_status
from training.treino.perda import (
    PerdaSegmentacao,
    percentual_do_gabarito,
    percentual_suave,
)
from training.treino.selecao import SelecaoMelhorPonto, chave_de_selecao

PESOS = torch.tensor([0.5, 0.8, 4.0])


def _logits(rotulos: torch.Tensor, margem: float = 12.0) -> torch.Tensor:
    """Logits que escolhem exatamente os rótulos dados."""
    return torch.nn.functional.one_hot(rotulos, 3).permute(0, 3, 1, 2).float() * margem


def _alvo(percentual: float, tamanho: int = 20) -> torch.Tensor:
    """Máscara com a metade de cima de placa e `percentual` dela coberta."""
    alvo = torch.zeros((1, tamanho, tamanho), dtype=torch.long)
    placa = tamanho * tamanho // 2
    alvo.view(-1)[:placa] = 1
    alvo.view(-1)[: round(placa * percentual / 100)] = 2
    return alvo


def test_perda_e_quase_zero_com_predicao_perfeita():
    alvo = _alvo(30.0)

    resultado = PerdaSegmentacao(PESOS, lambda_area=1.0)(_logits(alvo), alvo)

    assert float(resultado.total) < 1e-3
    assert float(resultado.area) < 1e-3


def test_prever_so_placa_limpa_tem_boa_acuracia_de_pixel_mas_perda_alta():
    """O cenário que uma CrossEntropy simples não penaliza o bastante."""
    alvo = _alvo(10.0)
    so_limpa = torch.where(alvo == 2, torch.ones_like(alvo), alvo)
    acuracia_pixel = float((so_limpa == alvo).float().mean())

    perfeita = PerdaSegmentacao(PESOS, lambda_area=0.0)(_logits(alvo), alvo)
    ingenua = PerdaSegmentacao(PESOS, lambda_area=0.0)(_logits(so_limpa), alvo)

    assert acuracia_pixel >= 0.94
    assert float(ingenua.dice) > float(perfeita.dice) + 0.3


def test_termo_de_area_mede_o_erro_do_percentual():
    alvo = _alvo(40.0)
    so_limpa = torch.where(alvo == 2, torch.ones_like(alvo), alvo)

    resultado = PerdaSegmentacao(PESOS, lambda_area=0.5)(_logits(so_limpa), alvo)

    assert float(resultado.area) == pytest.approx(0.40, abs=0.02)
    assert float(resultado.total) > float(
        PerdaSegmentacao(PESOS, lambda_area=0.0)(_logits(so_limpa), alvo).total
    )


def test_lambda_zero_desliga_o_termo_de_area():
    alvo = _alvo(40.0)
    so_limpa = torch.where(alvo == 2, torch.ones_like(alvo), alvo)

    resultado = PerdaSegmentacao(PESOS, lambda_area=0.0)(_logits(so_limpa), alvo)

    assert float(resultado.area) == 0.0


def test_perda_e_diferenciavel():
    alvo = _alvo(30.0)
    logits = torch.randn(1, 3, 20, 20, requires_grad=True)

    PerdaSegmentacao(PESOS, lambda_area=0.5)(logits, alvo).total.backward()

    assert logits.grad is not None and torch.isfinite(logits.grad).all()


def test_percentual_suave_e_do_gabarito_concordam_com_predicao_perfeita():
    alvo = _alvo(25.0)

    suave = percentual_suave(_logits(alvo).softmax(dim=1))

    assert float(suave[0]) == pytest.approx(
        float(percentual_do_gabarito(alvo)[0]), abs=1e-3
    )


def test_status_respeita_as_fronteiras_do_modelo_spec():
    assert derivar_status(39.99) == "ok"
    assert derivar_status(40.0) == "atencao"
    assert derivar_status(70.0) == "atencao"
    assert derivar_status(70.01) == "trocar"


def test_metricas_de_predicao_perfeita():
    alvo = torch.cat([_alvo(20.0), _alvo(55.0), _alvo(85.0)])
    acumulador = AcumuladorMetricas()

    acumulador.atualizar(_logits(alvo), alvo, [10.0, 40.0, 70.0], ["a", "a", "b"])
    resultado = acumulador.resultado()

    assert resultado["dice_coberta"] == pytest.approx(1.0)
    assert resultado["erro_percentual_medio_pp"] == pytest.approx(0.0, abs=0.5)
    assert resultado["acuracia_status"] == 1.0
    assert resultado["trocar_como_ok"] == 0
    assert set(resultado["erro_por_idade_pp"]) == {"0-30", "30-60", "60+"}


def test_trocar_classificado_como_ok_e_contado_como_erro_critico():
    alvo = _alvo(85.0)
    so_limpa = torch.where(alvo == 2, torch.ones_like(alvo), alvo)
    acumulador = AcumuladorMetricas()

    acumulador.atualizar(_logits(so_limpa), alvo, [80.0], ["a"])
    resultado = acumulador.resultado()

    assert resultado["trocar_como_ok"] == 1
    assert resultado["erro_percentual_medio_pp"] == pytest.approx(85.0, abs=1.0)
    assert resultado["matriz_status"][2][0] == 1
    assert resultado["dice_coberta"] == pytest.approx(0.0, abs=1e-6)


def test_falha_de_deteccao_da_placa_e_contada():
    alvo = _alvo(50.0)
    tudo_fundo = torch.zeros_like(alvo)
    acumulador = AcumuladorMetricas()

    acumulador.atualizar(_logits(tudo_fundo), alvo, [5.0], ["a"])

    assert acumulador.resultado()["falhas_deteccao_placa"] == 1


def _metricas(critico: int, erro: float, dice: float) -> dict:
    return {
        "trocar_como_ok": critico,
        "erro_percentual_medio_pp": erro,
        "dice_coberta": dice,
    }


def test_chave_prioriza_erro_critico_depois_erro_percentual_depois_dice():
    sem_critico = chave_de_selecao(_metricas(0, 9.0, 0.5))
    com_critico = chave_de_selecao(_metricas(1, 1.0, 0.99))
    mesmo_erro_melhor_dice = chave_de_selecao(_metricas(0, 9.0, 0.7))

    assert sem_critico < com_critico
    assert mesmo_erro_melhor_dice < sem_critico


def test_selecao_guarda_o_melhor_ponto_e_para_apos_a_paciencia():
    selecao = SelecaoMelhorPonto(paciencia=2, melhora_minima_pp=0.05)

    primeira = selecao.atualizar(_metricas(0, 5.0, 0.8))
    pior = selecao.atualizar(_metricas(0, 6.0, 0.8))
    ainda_pior = selecao.atualizar(_metricas(0, 6.5, 0.8))

    assert primeira.melhor_ponto and not primeira.parar
    assert not pior.melhor_ponto and not pior.parar and pior.epocas_sem_melhora == 1
    assert ainda_pior.parar


def test_melhora_menor_que_o_minimo_nao_zera_a_paciencia_mas_vira_melhor_ponto():
    selecao = SelecaoMelhorPonto(paciencia=3, melhora_minima_pp=0.05)
    selecao.atualizar(_metricas(0, 5.00, 0.8))

    pequena = selecao.atualizar(_metricas(0, 4.98, 0.8))

    assert pequena.melhor_ponto
    assert pequena.epocas_sem_melhora == 1


def test_melhora_relevante_zera_a_paciencia():
    selecao = SelecaoMelhorPonto(paciencia=3, melhora_minima_pp=0.05)
    selecao.atualizar(_metricas(0, 5.0, 0.8))
    selecao.atualizar(_metricas(0, 5.1, 0.8))

    boa = selecao.atualizar(_metricas(0, 4.0, 0.8))

    assert boa.epocas_sem_melhora == 0


def test_reduzir_o_erro_critico_conta_como_melhora_mesmo_com_erro_percentual_maior():
    selecao = SelecaoMelhorPonto(paciencia=2, melhora_minima_pp=0.05)
    selecao.atualizar(_metricas(2, 3.0, 0.9))

    decisao = selecao.atualizar(_metricas(1, 8.0, 0.7))

    assert decisao.melhor_ponto
    assert decisao.epocas_sem_melhora == 0


def test_melhor_ponto_por_dice_e_independente():
    selecao = SelecaoMelhorPonto(paciencia=5, melhora_minima_pp=0.05)
    selecao.atualizar(_metricas(0, 5.0, 0.80))

    decisao = selecao.atualizar(_metricas(0, 7.0, 0.95))

    assert not decisao.melhor_ponto
    assert decisao.melhor_por_dice
