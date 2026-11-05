import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { LIMITE_INATIVIDADE_MS, lerUltimaAtividade, registrarAtividade } from '../lib/inatividade'
import { INTERVALO_RENOVACAO_MS, useInatividade } from './useInatividade'

const MINUTO = 60_000

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-11-05T12:00:00Z'))
})

afterEach(() => {
  vi.useRealTimers()
})

function montar(ativo = true) {
  const aoExpirar = vi.fn()
  const aoRenovar = vi.fn()
  const hook = renderHook(({ ligado }) => useInatividade(ligado, aoExpirar, aoRenovar), {
    initialProps: { ligado: ativo },
  })
  return { aoExpirar, aoRenovar, ...hook }
}

describe('useInatividade', () => {
  it('encerra depois de 20 minutos sem nenhum uso, uma única vez', () => {
    const { aoExpirar } = montar()

    act(() => vi.advanceTimersByTime(LIMITE_INATIVIDADE_MS - MINUTO))
    expect(aoExpirar).not.toHaveBeenCalled()

    act(() => vi.advanceTimersByTime(2 * MINUTO))
    expect(aoExpirar).toHaveBeenCalledTimes(1)

    act(() => vi.advanceTimersByTime(10 * MINUTO))
    expect(aoExpirar).toHaveBeenCalledTimes(1)
  })

  it('reinicia a contagem a cada toque, tecla ou rolagem', () => {
    const { aoExpirar } = montar()

    act(() => vi.advanceTimersByTime(15 * MINUTO))
    act(() => window.dispatchEvent(new Event('pointerdown')))
    act(() => vi.advanceTimersByTime(15 * MINUTO))
    expect(aoExpirar).not.toHaveBeenCalled()

    act(() => window.dispatchEvent(new Event('keydown')))
    act(() => vi.advanceTimersByTime(19 * MINUTO))
    expect(aoExpirar).not.toHaveBeenCalled()

    act(() => vi.advanceTimersByTime(2 * MINUTO))
    expect(aoExpirar).toHaveBeenCalledTimes(1)
  })

  it('encerra ao voltar do segundo plano depois do limite, mesmo sem temporizador', () => {
    const { aoExpirar } = montar()

    // Com o app em segundo plano os temporizadores não rodam: só o relógio avança.
    vi.setSystemTime(Date.now() + 30 * MINUTO)
    act(() => document.dispatchEvent(new Event('visibilitychange')))

    expect(aoExpirar).toHaveBeenCalledTimes(1)
  })

  it('um toque depois do limite não revive a sessão', () => {
    const { aoExpirar } = montar()

    vi.setSystemTime(Date.now() + 25 * MINUTO)
    act(() => window.dispatchEvent(new Event('touchstart')))

    expect(aoExpirar).toHaveBeenCalledTimes(1)
    expect(Date.now() - (lerUltimaAtividade() ?? 0)).toBeGreaterThanOrEqual(25 * MINUTO)
  })

  it('renova a sessão no servidor no máximo a cada 5 minutos enquanto há uso', () => {
    const { aoRenovar } = montar()

    act(() => window.dispatchEvent(new Event('pointerdown')))
    expect(aoRenovar).not.toHaveBeenCalled()

    act(() => vi.advanceTimersByTime(INTERVALO_RENOVACAO_MS + 1_000))
    act(() => window.dispatchEvent(new Event('pointerdown')))
    expect(aoRenovar).toHaveBeenCalledTimes(1)

    act(() => window.dispatchEvent(new Event('pointerdown')))
    expect(aoRenovar).toHaveBeenCalledTimes(1)
  })

  it('não vigia nada enquanto está desligado', () => {
    registrarAtividade(Date.now() - 60 * MINUTO)
    const { aoExpirar } = montar(false)

    act(() => vi.advanceTimersByTime(30 * MINUTO))
    act(() => document.dispatchEvent(new Event('visibilitychange')))

    expect(aoExpirar).not.toHaveBeenCalled()
  })
})
