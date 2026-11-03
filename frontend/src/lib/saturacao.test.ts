import { describe, expect, it } from 'vitest'
import { formatIndiceSaturacao, indiceSaturacao } from './saturacao'

describe('indiceSaturacao', () => {
  it.each([
    [0, 0],
    [5, 20],
    [10, 40],
    [20, 80],
    [25, 100],
    [54, 100],
  ])('cobertura %s resulta em índice %s', (cobertura, indice) => {
    expect(indiceSaturacao(cobertura)).toBe(indice)
  })

  it('usa o limiar informado', () => {
    expect(indiceSaturacao(30, 30)).toBe(80)
    expect(indiceSaturacao(15, 30)).toBe(40)
  })

  it('cai no limiar padrão quando o limiar é zero ou negativo', () => {
    expect(indiceSaturacao(20, 0)).toBe(80)
    expect(indiceSaturacao(20, -5)).toBe(80)
  })

  it('limita o resultado entre 0 e 100', () => {
    expect(indiceSaturacao(-3)).toBe(0)
    expect(indiceSaturacao(100)).toBe(100)
  })
})

describe('formatIndiceSaturacao', () => {
  it('formata com duas casas e vírgula', () => {
    expect(formatIndiceSaturacao(20)).toBe('80,00%')
    expect(formatIndiceSaturacao(12.5)).toBe('50,00%')
  })

  it('devolve um traço sem medição', () => {
    expect(formatIndiceSaturacao(null)).toBe('—')
  })
})
