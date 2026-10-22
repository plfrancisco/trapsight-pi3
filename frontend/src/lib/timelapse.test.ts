import { describe, expect, it } from 'vitest'
import {
  indiceQuadroMaisProximo,
  instanteDoQuadro,
  instantesTroca,
  limitarVelocidade,
  mapearArrastoParaIndice,
  proximoIndice,
  VELOCIDADE_MAX_MS,
  VELOCIDADE_MIN_MS,
  VELOCIDADE_PADRAO_MS,
} from './timelapse'

describe('funções de timelapse', () => {
  it('limita a velocidade à faixa permitida e usa o padrão para valor inválido', () => {
    expect(VELOCIDADE_PADRAO_MS).toBe(500)
    expect(VELOCIDADE_MIN_MS).toBe(200)
    expect(VELOCIDADE_MAX_MS).toBe(2000)
    expect(limitarVelocidade(100)).toBe(200)
    expect(limitarVelocidade(900)).toBe(900)
    expect(limitarVelocidade(2500)).toBe(2000)
    expect(limitarVelocidade(Number.NaN)).toBe(500)
  })

  it('avança até o último item e para em listas de um ou vários quadros', () => {
    expect(proximoIndice(0, 1)).toBeNull()
    expect(proximoIndice(0, 3)).toBe(1)
    expect(proximoIndice(1, 3)).toBe(2)
    expect(proximoIndice(2, 3)).toBeNull()
    expect(proximoIndice(0, 0)).toBeNull()
  })

  it('encontra o quadro temporal mais próximo em listas de um ou vários itens', () => {
    expect(indiceQuadroMaisProximo([1000], 1200)).toBe(0)
    expect(indiceQuadroMaisProximo([1000, 3000, 5000], 3900)).toBe(1)
    expect(indiceQuadroMaisProximo([1000, 3000], 2000)).toBe(0)
    expect(indiceQuadroMaisProximo([], 2000)).toBe(-1)
  })

  it('mapeia um arrasto para a análise mais próxima', () => {
    expect(mapearArrastoParaIndice([1000, 3000, 5000], 4600)).toBe(2)
  })

  it('obtém o instante de um quadro sem aceitar índices inexistentes', () => {
    expect(instanteDoQuadro([1000, 3000], 1)).toBe(3000)
    expect(instanteDoQuadro([1000], 0)).toBe(1000)
    expect(instanteDoQuadro([], 0)).toBeNull()
    expect(instanteDoQuadro([1000], 2)).toBeNull()
  })

  it('gera uma marca por data de troca válida', () => {
    const trocas = instantesTroca([
      { data_troca: '2026-08-01' },
      { data_troca: '2026-09-15' },
    ])

    expect(trocas).toHaveLength(2)
    expect(trocas.every(Number.isFinite)).toBe(true)
  })
})
