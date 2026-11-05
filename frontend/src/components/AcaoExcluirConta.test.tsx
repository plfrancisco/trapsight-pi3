import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../services/erros'
import AcaoExcluirConta from './AcaoExcluirConta'

vi.mock('../services/usuarios', async (original) => ({
  ...await original<typeof import('../services/usuarios')>(),
  deleteUsuario: vi.fn(),
}))

import { deleteUsuario } from '../services/usuarios'

function renderAcao(onExcluida = vi.fn()) {
  render(
    <AcaoExcluirConta
      email="ana@exemplo.com"
      nome="Ana Souza"
      onExcluida={onExcluida}
      usuarioId="u1"
    />,
  )
  return onExcluida
}

describe('AcaoExcluirConta', () => {
  beforeEach(() => {
    vi.mocked(deleteUsuario).mockReset()
  })

  it('não mostra a confirmação nem repete o e-mail antes de abrir', () => {
    renderAcao()

    expect(screen.getByRole('button', { name: 'Excluir conta de Ana Souza' })).toBeVisible()
    expect(screen.queryByText('ana@exemplo.com')).not.toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('pede confirmação, avisa que não há volta e só exclui depois de confirmar', async () => {
    const usuario = userEvent.setup()
    vi.mocked(deleteUsuario).mockResolvedValue(undefined)
    const onExcluida = renderAcao()

    await usuario.click(screen.getByRole('button', { name: 'Excluir conta de Ana Souza' }))

    const dialogo = screen.getByRole('dialog', { name: 'Excluir a conta de Ana Souza?' })
    expect(dialogo).toHaveTextContent('ana@exemplo.com')
    expect(dialogo).toHaveTextContent('Essa ação não pode ser desfeita')
    expect(deleteUsuario).not.toHaveBeenCalled()

    await usuario.click(within(dialogo).getByRole('button', { name: 'Confirmar exclusão' }))

    await waitFor(() => expect(deleteUsuario).toHaveBeenCalledWith('u1'))
    await waitFor(() => expect(onExcluida).toHaveBeenCalledTimes(1))
  })

  it('cancelar fecha o diálogo sem chamar a API', async () => {
    const usuario = userEvent.setup()
    const onExcluida = renderAcao()

    await usuario.click(screen.getByRole('button', { name: 'Excluir conta de Ana Souza' }))
    await usuario.click(screen.getByRole('button', { name: 'Cancelar' }))

    expect(deleteUsuario).not.toHaveBeenCalled()
    expect(onExcluida).not.toHaveBeenCalled()
    expect(screen.queryByText('ana@exemplo.com')).not.toBeInTheDocument()
  })

  it('mostra o erro pelo código, mantém o diálogo aberto e não avisa que excluiu', async () => {
    const usuario = userEvent.setup()
    vi.mocked(deleteUsuario).mockRejectedValue(
      new ApiError('CONTA_NAO_ENCONTRADA', 'texto interno', 404),
    )
    const onExcluida = renderAcao()

    await usuario.click(screen.getByRole('button', { name: 'Excluir conta de Ana Souza' }))
    await usuario.click(screen.getByRole('button', { name: 'Confirmar exclusão' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Esta conta já foi removida ou não existe.',
    )
    expect(screen.queryByText('texto interno')).not.toBeInTheDocument()
    expect(screen.getByRole('dialog')).toBeVisible()
    expect(onExcluida).not.toHaveBeenCalled()
  })

  it('impede um segundo envio enquanto a exclusão está em andamento', async () => {
    const usuario = userEvent.setup()
    vi.mocked(deleteUsuario).mockReturnValue(new Promise(() => undefined))
    renderAcao()

    await usuario.click(screen.getByRole('button', { name: 'Excluir conta de Ana Souza' }))
    await usuario.click(screen.getByRole('button', { name: 'Confirmar exclusão' }))

    await waitFor(() => expect(screen.getByRole('button', { name: 'Excluindo…' })).toBeDisabled())
    expect(deleteUsuario).toHaveBeenCalledTimes(1)
  })
})
