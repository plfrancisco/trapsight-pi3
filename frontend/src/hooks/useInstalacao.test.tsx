import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useInstalacao, useModoInstalado } from './useInstalacao'

const consultaDisplayMode = '(display-mode: standalone)'
const descritorMatchMedia = Object.getOwnPropertyDescriptor(window, 'matchMedia')
const descritorUserAgent = Object.getOwnPropertyDescriptor(navigator, 'userAgent')
const descritorToques = Object.getOwnPropertyDescriptor(navigator, 'maxTouchPoints')

function definirMatchMedia(valorInicial: boolean) {
  let ouvinte: ((evento: MediaQueryListEvent) => void) | null = null
  const consulta = {
    matches: valorInicial,
    media: consultaDisplayMode,
    onchange: null,
    addEventListener: vi.fn((_tipo: string, callback: (evento: MediaQueryListEvent) => void) => {
      ouvinte = callback
    }),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }

  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: vi.fn(() => consulta as unknown as MediaQueryList),
  })

  return {
    consulta,
    emitirMudanca(instalado: boolean) {
      consulta.matches = instalado
      ouvinte?.({ matches: instalado } as MediaQueryListEvent)
    },
  }
}

function restaurarDescritor(
  alvo: object,
  nome: string,
  descritor: PropertyDescriptor | undefined,
) {
  if (descritor) Object.defineProperty(alvo, nome, descritor)
  else Reflect.deleteProperty(alvo, nome)
}

beforeEach(() => {
  Object.defineProperty(navigator, 'userAgent', {
    configurable: true,
    value: 'Mozilla/5.0 (Linux; Android 15; Pixel 9) Chrome/132.0 Mobile',
  })
})

afterEach(() => {
  window.dispatchEvent(new Event('appinstalled'))
  restaurarDescritor(window, 'matchMedia', descritorMatchMedia)
  restaurarDescritor(navigator, 'userAgent', descritorUserAgent)
  restaurarDescritor(navigator, 'maxTouchPoints', descritorToques)
})

describe('useModoInstalado', () => {
  it('acompanha a mudança para o modo standalone', () => {
    const media = definirMatchMedia(false)
    const { result, unmount } = renderHook(useModoInstalado)

    expect(result.current).toBe(false)
    act(() => media.emitirMudanca(true))
    expect(result.current).toBe(true)

    unmount()
    expect(media.consulta.removeEventListener).toHaveBeenCalledWith(
      'change',
      expect.any(Function),
    )
  })

  it('identifica o modo instalado do Safari no iOS', () => {
    Object.defineProperty(navigator, 'userAgent', {
      configurable: true,
      value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Mobile',
    })
    Object.defineProperty(navigator, 'standalone', { configurable: true, value: true })
    definirMatchMedia(false)

    const { result, unmount } = renderHook(useModoInstalado)
    expect(result.current).toBe(true)

    unmount()
    Reflect.deleteProperty(navigator, 'standalone')
  })
})

describe('useInstalacao', () => {
  it('captura o evento do navegador e abre o prompt quando solicitado', async () => {
    definirMatchMedia(false)
    const { result, unmount } = renderHook(useInstalacao)
    const prompt = vi.fn().mockResolvedValue(undefined)
    const evento = Object.assign(new Event('beforeinstallprompt', { cancelable: true }), {
      platforms: ['web'],
      prompt,
      userChoice: Promise.resolve({ outcome: 'accepted' as const, platform: 'web' }),
    })

    act(() => window.dispatchEvent(evento))
    expect(evento.defaultPrevented).toBe(true)
    expect(result.current.podeInstalar).toBe(true)

    await act(async () => result.current.instalar())
    expect(prompt).toHaveBeenCalledTimes(1)
    expect(result.current.instalado).toBe(true)
    expect(result.current.podeInstalar).toBe(false)

    unmount()
  })

  it('reconhece um iPad que apresenta o userAgent de desktop', () => {
    Object.defineProperty(navigator, 'userAgent', {
      configurable: true,
      value: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) Safari/605.1.15',
    })
    Object.defineProperty(navigator, 'maxTouchPoints', { configurable: true, value: 5 })
    definirMatchMedia(false)

    const { result, unmount } = renderHook(useInstalacao)
    expect(result.current.ehIos).toBe(true)

    unmount()
  })
})
