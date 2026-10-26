import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it, vi } from 'vitest'
import { ApiError } from '../services/erros'
import { createUsuario, listUsuarios } from '../services/usuarios'
import type { Conta } from '../services/tipos'
import ContasPage from './ContasPage'

vi.mock('../services/usuarios', async (original) => ({
  ...await original<typeof import('../services/usuarios')>(),
  createUsuario: vi.fn(),
  listUsuarios: vi.fn(),
}))

const conta: Conta = {
  id: 'u1', email: 'nova@exemplo.com', nome: 'Nova Pessoa',
  papel: 'operador', ativo: true, ultimo_login_em: null,
  criado_em: '2026-10-26T12:00:00Z',
}

beforeEach(() => {
  vi.mocked(listUsuarios).mockReset().mockResolvedValue([])
  vi.mocked(createUsuario).mockReset().mockResolvedValue(conta)
})

async function preencher() {
  const pessoa = userEvent.setup()
  await pessoa.type(screen.getByLabelText(/^Nome/), conta.nome)
  await pessoa.type(screen.getByLabelText(/^E-mail/), conta.email)
  await pessoa.type(screen.getByLabelText(/^Senha inicial/), 'uma frase longa e segura 2026')
  return pessoa
}

it('mostra lista vazia e cria operador sem campo de papel', async () => {
  render(<ContasPage />)
  expect(await screen.findByText('Nenhuma conta cadastrada.')).toBeVisible()
  const pessoa = await preencher()
  vi.mocked(listUsuarios).mockResolvedValue([conta])
  await pessoa.click(screen.getByRole('button', { name: 'Criar operador' }))
  expect(await screen.findByRole('status')).toHaveTextContent('Conta criada')
  expect(await screen.findByText(conta.email)).toBeVisible()
  expect(createUsuario).toHaveBeenCalledWith({
    nome: conta.nome, email: conta.email, senha: 'uma frase longa e segura 2026',
  })
  expect(screen.getByLabelText(/^Senha inicial/)).toHaveValue('')
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
})

it('expõe erro por código e permite tentar novamente sem revelar a senha', async () => {
  vi.mocked(createUsuario).mockRejectedValue(new ApiError('EMAIL_JA_CADASTRADO', 'texto interno', 409))
  render(<ContasPage />)
  await screen.findByText('Nenhuma conta cadastrada.')
  const pessoa = await preencher()
  await pessoa.click(screen.getByRole('button', { name: 'Criar operador' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Já existe uma conta com este e-mail')
  expect(screen.queryByText('texto interno')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Criar operador' })).toBeEnabled()
})

it('oferece nova tentativa se a listagem falhar', async () => {
  vi.mocked(listUsuarios).mockRejectedValueOnce(new ApiError('FALHA_DE_REDE', 'x', 0))
  render(<ContasPage />)
  await screen.findByRole('alert')
  await userEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }))
  expect(await screen.findByText('Nenhuma conta cadastrada.')).toBeVisible()
})

it('bloqueia outro envio enquanto aguarda a criação', async () => {
  vi.mocked(createUsuario).mockReturnValue(new Promise(() => undefined))
  render(<ContasPage />)
  await screen.findByText('Nenhuma conta cadastrada.')
  const pessoa = await preencher()
  await pessoa.click(screen.getByRole('button', { name: 'Criar operador' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Criando…' })).toBeDisabled())
  expect(createUsuario).toHaveBeenCalledTimes(1)
})
