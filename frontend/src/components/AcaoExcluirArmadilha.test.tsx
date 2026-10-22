import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AcaoExcluirArmadilha from './AcaoExcluirArmadilha'

vi.mock('../services/armadilhas', () => ({ deleteArmadilha: vi.fn() }))

import { deleteArmadilha } from '../services/armadilhas'

function CaminhoAtual() {
  return <output>{useLocation().pathname}</output>
}

function renderAcao() {
  return render(
    <MemoryRouter initialEntries={['/armadilhas/arm-1']}>
      <Routes>
        <Route
          element={
            <>
              <AcaoExcluirArmadilha armadilhaId="arm-1" identificador="ARM-001" />
              <CaminhoAtual />
            </>
          }
          path="/armadilhas/arm-1"
        />
        <Route element={<p>Painel de armadilhas</p>} path="/" />
      </Routes>
    </MemoryRouter>,
  )
}

describe('AcaoExcluirArmadilha', () => {
  beforeEach(() => {
    vi.mocked(deleteArmadilha).mockReset()
  })

  it('explica a preservação do histórico, pede confirmação e volta ao painel após excluir', async () => {
    const usuario = userEvent.setup()
    vi.mocked(deleteArmadilha).mockResolvedValue(undefined)
    renderAcao()

    await usuario.click(screen.getByRole('button', { name: 'Excluir armadilha' }))

    const dialogo = screen.getByRole('dialog', { name: 'Remover ARM-001 do painel?' })
    expect(dialogo).toHaveAttribute('open')
    expect(dialogo).toHaveTextContent('As análises e os históricos de refil continuarão salvos')
    expect(deleteArmadilha).not.toHaveBeenCalled()

    await usuario.click(within(dialogo).getByRole('button', { name: 'Confirmar remoção' }))

    await waitFor(() => expect(deleteArmadilha).toHaveBeenCalledWith('arm-1'))
    expect(await screen.findByText('Painel de armadilhas')).toBeVisible()
  })
})
