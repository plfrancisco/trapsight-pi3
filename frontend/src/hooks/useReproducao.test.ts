import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useReproducao } from './useReproducao'

describe('useReproducao', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('avança um quadro por intervalo padrão e para no último', () => {
    const { result } = renderHook(() => useReproducao(3, 500))

    act(() => result.current.playTimelapse())
    expect(result.current.reproduzindo).toBe(true)

    act(() => vi.advanceTimersByTime(499))
    expect(result.current.indiceQuadro).toBe(0)
    act(() => vi.advanceTimersByTime(1))
    expect(result.current.indiceQuadro).toBe(1)
    act(() => vi.advanceTimersByTime(500))

    expect(result.current.indiceQuadro).toBe(2)
    expect(result.current.reproduzindo).toBe(false)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('recomeça pelo primeiro quadro quando reproduzido a partir do último', () => {
    const { result } = renderHook(() => useReproducao(2, 500))

    act(() => result.current.playTimelapse())
    act(() => vi.advanceTimersByTime(500))
    expect(result.current.indiceQuadro).toBe(1)
    expect(result.current.reproduzindo).toBe(false)

    act(() => result.current.playTimelapse())
    expect(result.current.indiceQuadro).toBe(0)
    expect(result.current.reproduzindo).toBe(true)
  })

  it('aplica uma nova velocidade ao próximo quadro', () => {
    const { result, rerender } = renderHook(
      ({ velocidadeMs }: { velocidadeMs: number }) => useReproducao(3, velocidadeMs),
      { initialProps: { velocidadeMs: 500 } },
    )

    act(() => result.current.playTimelapse())
    act(() => vi.advanceTimersByTime(300))
    rerender({ velocidadeMs: 200 })

    act(() => vi.advanceTimersByTime(199))
    expect(result.current.indiceQuadro).toBe(0)
    act(() => vi.advanceTimersByTime(1))
    expect(result.current.indiceQuadro).toBe(1)
  })

  it('cancela o avanço quando pausado', () => {
    const { result } = renderHook(() => useReproducao(3, 500))

    act(() => result.current.playTimelapse())
    act(() => vi.advanceTimersByTime(200))
    act(() => result.current.pauseTimelapse())
    act(() => vi.advanceTimersByTime(1000))

    expect(result.current.indiceQuadro).toBe(0)
    expect(result.current.reproduzindo).toBe(false)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('limpa o temporizador ao desmontar', () => {
    const { result, unmount } = renderHook(() => useReproducao(3, 500))

    act(() => result.current.playTimelapse())
    expect(vi.getTimerCount()).toBe(1)

    unmount()

    expect(vi.getTimerCount()).toBe(0)
    act(() => vi.advanceTimersByTime(1000))
  })
})
