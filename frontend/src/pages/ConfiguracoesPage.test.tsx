import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Outlet, Route, Routes } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import type { Tema } from '../hooks/useTema'
import ConfiguracoesPage from './ConfiguracoesPage'

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
})
