import { describe, expect, it } from 'vitest'
import { buildResumoCobertura, buildSerieCobertura } from './cobertura'

describe('série de saturação', () => {
  it('preserva a ordem cronológica e converte a cobertura em índice de saturação', () => {
    const analises = [
      { analisado_em: '2026-10-14T08:00:00Z', percentual_coberto: 5 },
      { analisado_em: '2026-10-16T08:00:00Z', percentual_coberto: 12.5 },
    ]

    expect(buildSerieCobertura(analises)).toEqual([
      { instante: Date.parse('2026-10-14T08:00:00Z'), percentual: 20 },
      { instante: Date.parse('2026-10-16T08:00:00Z'), percentual: 50 },
    ])
  })

  it('usa o limiar de troca informado e limita o índice a 100', () => {
    const analises = [
      { analisado_em: '2026-10-14T08:00:00Z', percentual_coberto: 30 },
      { analisado_em: '2026-10-16T08:00:00Z', percentual_coberto: 90 },
    ]

    expect(buildSerieCobertura(analises, 30).map((ponto) => ponto.percentual)).toEqual([80, 100])
  })

  it('retorna uma série vazia sem sintetizar medições', () => {
    expect(buildSerieCobertura([])).toEqual([])
    expect(buildResumoCobertura([])).toBe('Evolução da saturação: 0 medições')
  })

  it('resume uma medição única com o índice de saturação', () => {
    expect(buildResumoCobertura([{ percentual_coberto: 10 }])).toBe(
      'Evolução da saturação: 1 medição, de 40,00% a 40,00%',
    )
  })

  it('descreve o índice da primeira e da última medição', () => {
    expect(
      buildResumoCobertura([
        { percentual_coberto: 5 },
        { percentual_coberto: 20 },
      ]),
    ).toBe('Evolução da saturação: 2 medições, de 20,00% a 80,00%')
  })
})
