import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Outlet, Route, Routes } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Tema } from '../hooks/useTema'
import ConfiguracoesPage from './ConfiguracoesPage'

const descritorMatchMedia = Object.getOwnPropertyDescriptor(window, 'matchMedia')
const descritorUserAgent = Object.getOwnPropertyDescriptor(navigator, 'userAgent')

function prepararNavegador(consultas: Record<string, boolean> = {}) {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: vi.fn((media: string) => ({
      matches: consultas[media] ?? false,
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

function definirUserAgent(valor: string) {
  Object.defineProperty(navigator, 'userAgent', { configurable: true, value: valor })
}

function restaurarDescritor(alvo: object, nome: string, descritor: PropertyDescriptor | undefined) {
  if (descritor) Object.defineProperty(alvo, nome, descritor)
  else Reflect.deleteProperty(alvo, nome)
}

beforeEach(() => {
  prepararNavegador()
  definirUserAgent('Mozilla/5.0 (Linux; Android 15; Pixel 9) Chrome/132.0 Mobile')
})

afterEach(() => {
  window.dispatchEvent(new Event('appinstalled'))
  restaurarDescritor(window, 'matchMedia', descritorMatchMedia)
  restaurarDescritor(navigator, 'userAgent', descritorUserAgent)
})

function renderizar(tema: Tema, alternarTema = vi.fn()) {
  render(
    <MemoryRouter initialEntries={['/configuracoes']}>
      <Routes>
        <Route element={<Outlet context={{ alternarTema, tema }} />}>
          <Route element={<ConfiguracoesPage />} path="/configuracoes" />
          <Route element={<p>Tela de troca de senha</p>} path="/conta/senha" />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
  return alternarTema
}

describe('ConfiguracoesPage', () => {
  it('mostra o tema atual como selecionado', () => {
    renderizar('claro')

    expect(screen.getByRole('heading', { name: 'Configurações', level: 1 })).toBeVisible()
    expect(screen.getByRole('button', { name: /Claro/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /Escuro/ })).toHaveAttribute('aria-pressed', 'false')
  })

  it('alterna o tema só quando a escolha é diferente da atual', async () => {
    const usuario = userEvent.setup()
    const alternarTema = renderizar('claro')

    await usuario.click(screen.getByRole('button', { name: /Claro/ }))
    expect(alternarTema).not.toHaveBeenCalled()

    await usuario.click(screen.getByRole('button', { name: /Escuro/ }))
    expect(alternarTema).toHaveBeenCalledTimes(1)
  })

  it('leva à troca de senha a partir da segurança da conta', async () => {
    const usuario = userEvent.setup()
    renderizar('escuro')

    expect(screen.getByRole('heading', { name: 'Segurança da conta' })).toBeVisible()
    await usuario.click(screen.getByRole('link', { name: /Alterar senha/ }))

    expect(await screen.findByText('Tela de troca de senha')).toBeVisible()
  })

  it('informa que o aplicativo já está instalado e oculta a ação', () => {
    prepararNavegador({ '(display-mode: standalone)': true })
    renderizar('escuro')

    expect(screen.getByRole('heading', { name: 'Aplicativo instalado' })).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Instalar aplicativo' })).not.toBeInTheDocument()
  })

  it('mostra as instruções de instalação no iPhone', () => {
    definirUserAgent('Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Mobile')
    renderizar('claro')

    expect(screen.getByText(/Compartilhar e depois em Adicionar à Tela de Início/)).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Instalar aplicativo' })).not.toBeInTheDocument()
  })

  it('aciona o diálogo nativo de instalação quando o navegador oferece o convite', async () => {
    const usuario = userEvent.setup()
    const prompt = vi.fn().mockResolvedValue(undefined)
    const evento = Object.assign(new Event('beforeinstallprompt', { cancelable: true }), {
      platforms: ['web'],
      prompt,
      userChoice: Promise.resolve({ outcome: 'dismissed' as const, platform: 'web' }),
    })
    renderizar('escuro')

    act(() => window.dispatchEvent(evento))
    await usuario.click(screen.getByRole('button', { name: 'Instalar aplicativo' }))

    expect(evento.defaultPrevented).toBe(true)
    expect(prompt).toHaveBeenCalledTimes(1)
  })
})
