import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
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
import { limparCsrf, obterCsrf } from '../services/sessao'
import AlterarSenhaPage from './AlterarSenhaPage'

const usuario = { troca_senha_pendente: false, papel: 'operador' as const, id: 'u1', email: 'ana@exemplo.com', nome: 'Ana' }
const nova = 'uma frase bem longa e unica'

const montar = () =>
  render(
    <MemoryRouter>
      <AuthProvider ativa>
        <AlterarSenhaPage />
      </AuthProvider>
    </MemoryRouter>,
  )

interface Campos {
  atual?: string
  novaSenha?: string
  confirmacao?: string
}

async function preencher({ atual = 'senha atual qualquer', novaSenha = nova, confirmacao }: Campos = {}) {
  const confirmar = confirmacao ?? novaSenha
  const pessoa = userEvent.setup()
  await screen.findByRole('heading', { name: 'Alterar senha' })
  await waitFor(() => expect(api.getSessao).toHaveBeenCalled())
  if (atual) await pessoa.type(screen.getByLabelText(/Senha atual/), atual)
  if (novaSenha) await pessoa.type(screen.getByLabelText(/^Nova senha/), novaSenha)
  if (confirmar) await pessoa.type(screen.getByLabelText(/Confirmar nova senha/), confirmar)
  await pessoa.click(screen.getByRole('button', { name: 'Alterar senha' }))
}

beforeEach(() => {
  vi.mocked(api.getSessao).mockReset()
  vi.mocked(api.getSessao).mockResolvedValue({ usuario, csrf_token: 'csrf-antigo' })
  vi.mocked(api.changeSenha).mockReset()
})

afterEach(() => limparCsrf())

describe('AlterarSenhaPage', () => {
  it('usa os atributos de preenchimento corretos para gerenciadores de senha', async () => {
    montar()
    await screen.findByRole('heading', { name: 'Alterar senha' })

    expect(screen.getByLabelText(/Senha atual/)).toHaveAttribute('autocomplete', 'current-password')
    expect(screen.getByLabelText(/^Nova senha/)).toHaveAttribute('autocomplete', 'new-password')
    expect(screen.getByLabelText(/Confirmar nova senha/)).toHaveAttribute('autocomplete', 'new-password')
  })

  it('explica o mínimo de caracteres sem impor regra de composição', async () => {
    montar()
    await screen.findByRole('heading', { name: 'Alterar senha' })

    expect(screen.getByText(/ao menos 15 caracteres/)).toBeVisible()
    expect(screen.queryByText(/maiúscula|símbolo|número/i)).not.toBeInTheDocument()
  })

  it('troca a senha, renova o token CSRF e confirma', async () => {
    vi.mocked(api.changeSenha).mockResolvedValue({ csrf_token: 'csrf-novo' })

    montar()
    await preencher()

    expect(await screen.findByRole('status')).toHaveTextContent('Senha alterada')
    expect(api.changeSenha).toHaveBeenCalledWith('senha atual qualquer', nova)
    expect(obterCsrf()).toBe('csrf-novo')
  })

  it('limpa os campos depois do sucesso', async () => {
    vi.mocked(api.changeSenha).mockResolvedValue({ csrf_token: 'csrf-novo' })

    montar()
    await preencher()
    await screen.findByRole('status')

    expect(screen.getByLabelText(/Senha atual/)).toHaveValue('')
    expect(screen.getByLabelText(/^Nova senha/)).toHaveValue('')
    expect(screen.getByLabelText(/Confirmar nova senha/)).toHaveValue('')
  })

  it('recusa senha curta antes de chamar a API', async () => {
    montar()
    await preencher({ novaSenha: 'curta demais', confirmacao: 'curta demais' })

    expect(await screen.findByRole('alert')).toHaveTextContent('pelo menos 15 caracteres')
    expect(api.changeSenha).not.toHaveBeenCalled()
  })

  it('recusa confirmação diferente antes de chamar a API', async () => {
    montar()
    await preencher({ confirmacao: nova + 'x' })

    expect(await screen.findByRole('alert')).toHaveTextContent('confirmação não confere')
    expect(api.changeSenha).not.toHaveBeenCalled()
  })

  it('exige a senha atual', async () => {
    montar()
    await preencher({ atual: '' })

    expect(await screen.findByRole('alert')).toHaveTextContent('Informe a senha atual')
    expect(api.changeSenha).not.toHaveBeenCalled()
  })

  it('indica a senha atual errada pelo código do erro', async () => {
    vi.mocked(api.changeSenha).mockRejectedValue(new ApiError('CREDENCIAIS_INVALIDAS', 'x', 401))

    montar()
    await preencher()

    expect(await screen.findByRole('alert')).toHaveTextContent('A senha atual está incorreta.')
    expect(obterCsrf()).toBe('csrf-antigo')
  })

  it('explica a política quando o servidor recusa por senha fraca, sem repetir a senha', async () => {
    vi.mocked(api.changeSenha).mockRejectedValue(
      new ApiError('SENHA_FRACA', `Senha fraca: ${nova}`, 422),
    )

    montar()
    await preencher()

    const alerta = await screen.findByRole('alert')
    expect(alerta).toHaveTextContent('não atende à política')
    expect(alerta).not.toHaveTextContent(nova)
  })

  it('explica que a nova senha deve ser diferente da atual', async () => {
    vi.mocked(api.changeSenha).mockRejectedValue(
      new ApiError('SENHA_FRACA', 'x', 422, { motivo: 'igual_atual' }),
    )

    montar()
    await preencher()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'A nova senha precisa ser diferente da senha atual.',
    )
  })

  it('não mostra confirmação de sucesso depois de uma falha posterior', async () => {
    vi.mocked(api.changeSenha).mockResolvedValueOnce({ csrf_token: 'c1' })
    montar()
    await preencher()
    await screen.findByRole('status')

    vi.mocked(api.changeSenha).mockRejectedValueOnce(new ApiError('SENHA_FRACA', 'x', 422))
    const pessoa = userEvent.setup()
    await pessoa.type(screen.getByLabelText(/Senha atual/), 'outra senha atual qualquer')
    await pessoa.type(screen.getByLabelText(/^Nova senha/), nova)
    await pessoa.type(screen.getByLabelText(/Confirmar nova senha/), nova)
    await pessoa.click(screen.getByRole('button', { name: 'Alterar senha' }))

    expect(await screen.findByRole('alert')).toBeVisible()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
