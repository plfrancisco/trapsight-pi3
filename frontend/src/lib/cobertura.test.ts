import { describe, expect, it } from 'vitest'
import { buildResumoCobertura, buildSerieCobertura } from './cobertura'

describe('série de cobertura', () => {
  it('preserva a ordem cronológica e os valores medidos pela API', () => {
    const analises = [
      { analisado_em: '2026-10-14T08:00:00Z', percentual_coberto: 27.5 },
      { analisado_em: '2026-10-16T08:00:00Z', percentual_coberto: 63.25 },
    ]

    expect(buildSerieCobertura(analises)).toEqual([
      { instante: Date.parse('2026-10-14T08:00:00Z'), percentual: 27.5 },
      { instante: Date.parse('2026-10-16T08:00:00Z'), percentual: 63.25 },
    ])
  })

  it('retorna uma série vazia sem sintetizar medições', () => {
    expect(buildSerieCobertura([])).toEqual([])
    expect(buildResumoCobertura([])).toBe('Evolução da cobertura: 0 medições')
  })

  it('resume uma medição única sem alterar o percentual', () => {
    expect(buildResumoCobertura([{ percentual_coberto: 42 }])).toBe(
      'Evolução da cobertura: 1 medição, de 42,00% a 42,00%',
    )
  })

  it('descreve os percentuais da primeira e última medição', () => {
    expect(
      buildResumoCobertura([
        { percentual_coberto: 27.5 },
        { percentual_coberto: 63.25 },
      ]),
    ).toBe('Evolução da cobertura: 2 medições, de 27,50% a 63,25%')
  })
})
