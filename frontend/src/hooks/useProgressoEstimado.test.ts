import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  faseDoProgresso,
  INTERVALO_PROGRESSO_MS,
  percentualEstimado,
  useProgressoEstimado,
} from './useProgressoEstimado'

describe('percentualEstimado', () => {
  it('começa em zero e sobe de forma monotônica', () => {
    expect(percentualEstimado(0)).toBe(0)
    expect(percentualEstimado(-500)).toBe(0)
    const amostras = [0, 500, 1000, 2000, 4000, 8000, 16000, 60000].map(percentualEstimado)
    for (let i = 1; i < amostras.length; i += 1) {
      expect(amostras[i]).toBeGreaterThan(amostras[i - 1])
    }
  })

  it('segue o ritmo de uma análise típica de cerca de 5 segundos', () => {
    expect(percentualEstimado(4000)).toBeCloseTo(56.9, 1)
    expect(percentualEstimado(5000)).toBeGreaterThan(60)
    expect(percentualEstimado(5000)).toBeLessThan(75)
  })

  it('nunca passa de 95% sem a resposta', () => {
    expect(percentualEstimado(10 * 60 * 1000)).toBeLessThanOrEqual(95)
    expect(percentualEstimado(Number.MAX_SAFE_INTEGER)).toBeLessThanOrEqual(95)
  })
})

describe('faseDoProgresso', () => {
  it('troca de fase nos limites de 15% e 100%', () => {
    expect(faseDoProgresso(0)).toBe('enviando')
    expect(faseDoProgresso(14.9)).toBe('enviando')
    expect(faseDoProgresso(15)).toBe('medindo')
    expect(faseDoProgresso(95)).toBe('medindo')
    expect(faseDoProgresso(100)).toBe('concluida')
  })
})

describe('useProgressoEstimado', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  function avancar(ms: number) {
    act(() => {
      vi.advanceTimersByTime(ms)
    })
  }

  it('parte de zero na fase de envio', () => {
    const { result } = renderHook(() => useProgressoEstimado(false))

    expect(result.current).toEqual({ percentual: 0, fase: 'enviando' })
  })

  it('sobe com o tempo, só para cima e abaixo de 95% enquanto a resposta não chega', () => {
    const { result } = renderHook(() => useProgressoEstimado(false))
    let anterior = 0

    for (let passo = 0; passo < 200; passo += 1) {
      avancar(INTERVALO_PROGRESSO_MS)
      expect(result.current.percentual).toBeGreaterThanOrEqual(anterior)
      expect(result.current.percentual).toBeLessThanOrEqual(95)
      anterior = result.current.percentual
    }

    expect(anterior).toBeGreaterThan(80)
    expect(result.current.fase).toBe('medindo')
  })

  it('vai a 100% e muda para concluída quando a resposta chega', () => {
    const { result, rerender } = renderHook(
      ({ concluido }) => useProgressoEstimado(concluido),
      { initialProps: { concluido: false } },
    )
    avancar(2000)
    expect(result.current.percentual).toBeLessThan(95)

    rerender({ concluido: true })

    expect(result.current).toEqual({ percentual: 100, fase: 'concluida' })
  })

  it('não deixa timer ativo ao desmontar', () => {
    const { unmount } = renderHook(() => useProgressoEstimado(false))

    unmount()

    expect(vi.getTimerCount()).toBe(0)
  })
})
