import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../services/auth', () => ({
  login: vi.fn(),
  logout: vi.fn(),
  getSessao: vi.fn(),
  changeSenha: vi.fn(),
}))

import AuthProvider from '../auth/AuthProvider'
import * as api from '../services/auth'
import { ApiError } from '../services/erros'
import Layout from './Layout'

const usuario = { troca_senha_pendente: false, papel: 'operador' as const, id: 'u1', email: 'ana@exemplo.com', nome: 'Ana Souza' }

const ABRIR_CONTA = 'Abrir opções da conta de Ana Souza'
const ouvintesDoModo = new Set<EventListenerOrEventListenerObject>()
let modoStandalone = false
let alterarModoStandalone: (instalado: boolean) => void = () => undefined

function configurarMatchMedia() {
  const consulta = {
    get matches() {
      return modoStandalone
    },
    media: '(display-mode: standalone)',
    onchange: null,
    addEventListener: (_tipo: string, ouvinte: EventListenerOrEventListenerObject) => {
      ouvintesDoModo.add(ouvinte)
    },
    removeEventListener: (_tipo: string, ouvinte: EventListenerOrEventListenerObject) => {
      ouvintesDoModo.delete(ouvinte)
    },
    addListener: (ouvinte: EventListener) => ouvintesDoModo.add(ouvinte),
    removeListener: (ouvinte: EventListener) => ouvintesDoModo.delete(ouvinte),
    dispatchEvent: () => true,
  } as unknown as MediaQueryList

  vi.stubGlobal('matchMedia', vi.fn(() => consulta))

  return (instalado: boolean) => {
    modoStandalone = instalado
    const evento = Object.assign(new Event('change'), { matches: instalado }) as MediaQueryListEvent
    ouvintesDoModo.forEach((ouvinte) => {
      if (typeof ouvinte === 'function') ouvinte(evento)
      else ouvinte.handleEvent(evento)
    })
  }
}

const montar = (ativa: boolean) =>
  render(
    <MemoryRouter>
      <AuthProvider ativa={ativa}>
        <Routes>
          <Route element={<Layout />}>
            <Route element={<p>Conteúdo</p>} path="/" />
          </Route>
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )

beforeEach(() => {
  vi.mocked(api.getSessao).mockReset()
  vi.mocked(api.logout).mockReset()
  modoStandalone = false
  ouvintesDoModo.clear()
  document.documentElement.removeAttribute('data-modo-instalado')
  alterarModoStandalone = configurarMatchMedia()
})

afterEach(() => {
  document.documentElement.removeAttribute('data-modo-instalado')
  vi.unstubAllGlobals()
})

describe('Layout e a conta do usuário', () => {
  it('mostra Contas nos dois menus somente ao gerente', async () => {
    vi.mocked(api.getSessao).mockResolvedValue({
      usuario: { ...usuario, papel: 'gerente' }, csrf_token: 'c',
    })
    montar(true)
    await screen.findAllByRole('button', { name: ABRIR_CONTA })
    expect(screen.getAllByRole('link', { name: 'Contas' })).toHaveLength(2)
  })

  it('não mostra Contas ao operador', async () => {
    vi.mocked(api.getSessao).mockResolvedValue({ usuario, csrf_token: 'c' })
    montar(true)
    await screen.findAllByRole('button', { name: ABRIR_CONTA })
    expect(screen.queryByRole('link', { name: 'Contas' })).not.toBeInTheDocument()
  })

  it('aplica e remove o modo visual instalado quando muda display-mode', async () => {
    montar(false)

    act(() => alterarModoStandalone(true))
    await waitFor(() =>
      expect(document.documentElement).toHaveAttribute('data-modo-instalado', 'true'),
    )

    act(() => alterarModoStandalone(false))
    await waitFor(() =>
      expect(document.documentElement).not.toHaveAttribute('data-modo-instalado'),
    )
  })

  it('mantém na barra móvel os mesmos destinos disponíveis ao gerente', async () => {
    vi.mocked(api.getSessao).mockResolvedValue({
      usuario: { ...usuario, papel: 'gerente' }, csrf_token: 'c',
    })
    montar(true)
    await screen.findAllByRole('button', { name: ABRIR_CONTA })

    const menuPrincipal = within(screen.getByRole('navigation', { name: 'Navegação principal' }))
    const menuMovel = within(screen.getByRole('navigation', { name: 'Navegação móvel' }))
    const destinosDesktop = menuPrincipal.getAllByRole('link').map((link) => link.getAttribute('href'))
    const destinosMoveis = menuMovel.getAllByRole('link').map((link) => link.getAttribute('href'))

    expect(destinosMoveis).toEqual(destinosDesktop)
    expect(destinosMoveis).toEqual(['/', '/analises/nova', '/armadilhas/nova', '/contas'])
  })

  it('põe o avatar da conta na barra móvel, com a logo ao lado da busca no topo', async () => {
    vi.mocked(api.getSessao).mockResolvedValue({ usuario, csrf_token: 'c' })
    const pessoa = userEvent.setup()
    montar(true)
    await screen.findAllByRole('button', { name: ABRIR_CONTA })

    const barraSuperior = within(screen.getByRole('banner', { name: 'Barra superior' }))
    expect(barraSuperior.queryByRole('button', { name: ABRIR_CONTA })).not.toBeInTheDocument()
    expect(barraSuperior.getByRole('link', { name: 'Ir para o início' })).toHaveAttribute('href', '/')

    const menuMovel = within(screen.getByRole('navigation', { name: 'Navegação móvel' }))
    const avatar = menuMovel.getByRole('button', { name: ABRIR_CONTA })
    expect(avatar).toHaveTextContent('Perfil')

    await pessoa.click(avatar)
    const menu = within(screen.getByLabelText('Opções da conta'))
    expect(menu.getByRole('link', { name: 'Configurações' })).toHaveAttribute('href', '/configuracoes')
    expect(menu.getByRole('button', { name: 'Sair' })).toBeVisible()
  })

  it('mostra o menu da conta com Configurações e Sair quando há sessão', async () => {
    vi.mocked(api.getSessao).mockResolvedValue({ usuario, csrf_token: 'c' })
    const pessoa = userEvent.setup()

    montar(true)
    const gatilhos = await screen.findAllByRole('button', { name: ABRIR_CONTA })
    expect(gatilhos).toHaveLength(2)
    expect(screen.queryByLabelText('Opções da conta')).not.toBeInTheDocument()

    await pessoa.click(gatilhos[0])

    const menu = screen.getByLabelText('Opções da conta')
    expect(menu).toHaveTextContent('Ana Souza')
    expect(within(menu).getByRole('link', { name: 'Configurações' })).toHaveAttribute('href', '/configuracoes')
    expect(within(menu).getByRole('button', { name: 'Sair' })).toBeVisible()
    expect(gatilhos[0]).toHaveAttribute('aria-expanded', 'true')
  })

  it('fecha o menu da conta com Escape e devolve o foco ao botão', async () => {
    vi.mocked(api.getSessao).mockResolvedValue({ usuario, csrf_token: 'c' })
    const pessoa = userEvent.setup()

    montar(true)
    const gatilho = (await screen.findAllByRole('button', { name: ABRIR_CONTA }))[0]
    await pessoa.click(gatilho)
    expect(screen.getByLabelText('Opções da conta')).toBeVisible()

    await pessoa.keyboard('{Escape}')

    expect(screen.queryByLabelText('Opções da conta')).not.toBeInTheDocument()
    expect(gatilho).toHaveFocus()
  })

  it('não mostra a área da conta com a autenticação desligada', () => {
    montar(false)

    expect(screen.queryByRole('button', { name: ABRIR_CONTA })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Sair' })).not.toBeInTheDocument()
    expect(screen.getByText('Conteúdo')).toBeVisible()
  })

  it('avisa quando não consegue encerrar a sessão e permanece conectado', async () => {
    vi.mocked(api.getSessao).mockResolvedValue({ usuario, csrf_token: 'c' })
    vi.mocked(api.logout).mockRejectedValue(new ApiError('FALHA_DE_REDE', 'x', 0))
    const pessoa = userEvent.setup()

    montar(true)
    await pessoa.click((await screen.findAllByRole('button', { name: ABRIR_CONTA }))[0])
    await pessoa.click(screen.getByRole('button', { name: 'Sair' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível encerrar a sessão')
    await waitFor(() =>
      expect(screen.getAllByRole('button', { name: ABRIR_CONTA })).toHaveLength(2),
    )
  })

  it('foca a busca do dashboard pelo atalho e limpa ao pressionar Escape', () => {
    montar(false)
    const busca = screen.getByRole('searchbox', { name: 'Buscar armadilha' })

    fireEvent.keyDown(window, { key: 'k', ctrlKey: true })
    expect(busca).toHaveFocus()

    fireEvent.change(busca, { target: { value: 'ARM-001' } })
    fireEvent.keyDown(busca, { key: 'Escape' })
    expect(busca).toHaveValue('')
    expect(busca).not.toHaveFocus()
  })
})
