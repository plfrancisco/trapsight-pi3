import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

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
})

describe('Layout e a conta do usuário', () => {
  it('mostra Contas nos dois menus somente ao gerente', async () => {
    vi.mocked(api.getSessao).mockResolvedValue({
      usuario: { ...usuario, papel: 'gerente' }, csrf_token: 'c',
    })
    montar(true)
    await screen.findByText(usuario.email)
    expect(screen.getAllByRole('link', { name: 'Contas' })).toHaveLength(2)
  })

  it('não mostra Contas ao operador', async () => {
    vi.mocked(api.getSessao).mockResolvedValue({ usuario, csrf_token: 'c' })
    montar(true)
    await screen.findByText(usuario.email)
    expect(screen.queryByRole('link', { name: 'Contas' })).not.toBeInTheDocument()
  })

  it('mostra e-mail, "Alterar senha" e "Sair" quando há sessão', async () => {
    vi.mocked(api.getSessao).mockResolvedValue({ usuario, csrf_token: 'c' })

    montar(true)

    expect(await screen.findByText('ana@exemplo.com')).toBeVisible()
    expect(screen.getAllByRole('link', { name: 'Alterar senha' })).toHaveLength(2)
    expect(screen.getAllByRole('link', { name: 'Alterar senha' })[0]).toHaveAttribute('href', '/conta/senha')
    expect(screen.getAllByRole('button', { name: 'Sair' })).toHaveLength(2)
  })

  it('não mostra a área da conta com a autenticação desligada', () => {
    montar(false)

    expect(screen.queryByRole('button', { name: 'Sair' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Alterar senha' })).not.toBeInTheDocument()
    expect(screen.getByText('Conteúdo')).toBeVisible()
  })

  it('avisa quando não consegue encerrar a sessão e permanece conectado', async () => {
    vi.mocked(api.getSessao).mockResolvedValue({ usuario, csrf_token: 'c' })
    vi.mocked(api.logout).mockRejectedValue(new ApiError('FALHA_DE_REDE', 'x', 0))
    const pessoa = userEvent.setup()

    montar(true)
    await pessoa.click((await screen.findAllByRole('button', { name: 'Sair' }))[0])

    expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível encerrar a sessão')
    await waitFor(() => expect(screen.getByText('ana@exemplo.com')).toBeVisible())
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
