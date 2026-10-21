import { render, screen, waitFor } from '@testing-library/react'
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

const usuario = { id: 'u1', email: 'ana@exemplo.com', nome: 'Ana Souza' }

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
  it('mostra e-mail, "Alterar senha" e "Sair" quando há sessão', async () => {
    vi.mocked(api.getSessao).mockResolvedValue({ usuario, csrf_token: 'c' })

    montar(true)

    expect(await screen.findByText('ana@exemplo.com')).toBeVisible()
    expect(screen.getByRole('link', { name: 'Alterar senha' })).toHaveAttribute('href', '/conta/senha')
    expect(screen.getByRole('button', { name: 'Sair' })).toBeVisible()
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
    await pessoa.click(await screen.findByRole('button', { name: 'Sair' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível encerrar a sessão')
    await waitFor(() => expect(screen.getByText('ana@exemplo.com')).toBeVisible())
  })
})
