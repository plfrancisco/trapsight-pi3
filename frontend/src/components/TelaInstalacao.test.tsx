import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import TelaInstalacao from './TelaInstalacao'

const CHAVE = 'trapsight:tela-instalacao-dispensada-em'
const UM_DIA = 24 * 60 * 60 * 1000
const ANDROID = 'Mozilla/5.0 (Linux; Android 15; Pixel 9) Chrome/132.0 Mobile'
const IPHONE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Mobile'
const DESKTOP = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/132.0'
const descritorUserAgent = Object.getOwnPropertyDescriptor(navigator, 'userAgent')
const descritorMatchMedia = Object.getOwnPropertyDescriptor(window, 'matchMedia')

function usarNavegador(userAgent: string, instalado = false) {
  Object.defineProperty(navigator, 'userAgent', { configurable: true, value: userAgent })
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: vi.fn((media: string) => ({
      matches: instalado && media === '(display-mode: standalone)',
      media,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }) as unknown as MediaQueryList),
  })
}

function criarEventoDeInstalacao() {
  const prompt = vi.fn().mockResolvedValue(undefined)
  const evento = Object.assign(new Event('beforeinstallprompt', { cancelable: true }), {
    platforms: ['web'],
    prompt,
    userChoice: Promise.resolve({ outcome: 'accepted' as const, platform: 'web' }),
  })
  return { evento, prompt }
}

function restaurar(alvo: object, nome: string, descritor: PropertyDescriptor | undefined) {
  if (descritor) Object.defineProperty(alvo, nome, descritor)
  else Reflect.deleteProperty(alvo, nome)
}

beforeEach(() => {
  window.dispatchEvent(new Event('appinstalled'))
  window.localStorage.removeItem(CHAVE)
})

afterEach(() => {
  window.dispatchEvent(new Event('appinstalled'))
  restaurar(navigator, 'userAgent', descritorUserAgent)
  restaurar(window, 'matchMedia', descritorMatchMedia)
  window.localStorage.removeItem(CHAVE)
  vi.restoreAllMocks()
})

describe('TelaInstalacao', () => {
  it('abre em tela cheia no Android e instala pelo convite do navegador', async () => {
    usarNavegador(ANDROID)
    const { evento, prompt } = criarEventoDeInstalacao()
    const pessoa = userEvent.setup()

    render(<TelaInstalacao />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    act(() => window.dispatchEvent(evento))
    const tela = await screen.findByRole('dialog', { name: 'Instale o TrapSight' })
    expect(tela).toBeVisible()

    await pessoa.click(screen.getByRole('button', { name: 'Instalar aplicativo' }))
    expect(prompt).toHaveBeenCalledTimes(1)
  })

  it('explica os passos no iPhone, onde não existe botão de instalar', async () => {
    usarNavegador(IPHONE)

    render(<TelaInstalacao />)

    expect(await screen.findByRole('dialog', { name: 'Instale o TrapSight' })).toBeVisible()
    expect(screen.getByText('Adicionar à Tela de Início')).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Instalar aplicativo' })).not.toBeInTheDocument()
  })

  it('não aparece no computador nem com o aplicativo já instalado', () => {
    usarNavegador(DESKTOP)
    const desktop = render(<TelaInstalacao />)
    act(() => window.dispatchEvent(criarEventoDeInstalacao().evento))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    desktop.unmount()

    usarNavegador(IPHONE, true)
    render(<TelaInstalacao />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('some ao continuar no navegador e só volta depois de 7 dias', async () => {
    usarNavegador(IPHONE)
    const pessoa = userEvent.setup()

    const primeira = render(<TelaInstalacao />)
    await pessoa.click(await screen.findByRole('button', { name: 'Continuar no navegador' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(Number(window.localStorage.getItem(CHAVE))).toBeGreaterThan(0)
    primeira.unmount()

    const segunda = render(<TelaInstalacao />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    segunda.unmount()

    window.localStorage.setItem(CHAVE, String(Date.now() - 8 * UM_DIA))
    render(<TelaInstalacao />)
    expect(await screen.findByRole('dialog', { name: 'Instale o TrapSight' })).toBeVisible()
  })

  it('fecha com Escape', async () => {
    usarNavegador(IPHONE)
    const pessoa = userEvent.setup()

    render(<TelaInstalacao />)
    await screen.findByRole('dialog')
    await pessoa.keyboard('{Escape}')

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
