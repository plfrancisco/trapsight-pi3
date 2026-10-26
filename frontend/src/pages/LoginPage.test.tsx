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
import LoginPage from './LoginPage'

const usuario = { papel: 'operador' as const, id: 'u1', email: 'ana@exemplo.com', nome: 'Ana' }

const montar = () =>
  render(
    <MemoryRouter initialEntries={['/login']}>
      <AuthProvider ativa>
        <Routes>
          <Route element={<LoginPage />} path="/login" />
          <Route element={<p>Página inicial</p>} path="/" />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )

async function preencher(email: string, senha: string) {
  const pessoa = userEvent.setup()
  await screen.findByRole('heading', { name: 'Entrar' })
  if (email) await pessoa.type(screen.getByLabelText(/E-mail/), email)
  if (senha) await pessoa.type(screen.getByLabelText(/Senha/), senha)
  await pessoa.click(screen.getByRole('button', { name: 'Entrar' }))
}

beforeEach(() => {
  vi.mocked(api.getSessao).mockReset()
  vi.mocked(api.getSessao).mockRejectedValue(new ApiError('NAO_AUTENTICADO', 'x', 401))
  vi.mocked(api.login).mockReset()
})

describe('LoginPage', () => {
  it('apresenta os campos com rótulo e os atributos de preenchimento corretos', async () => {
    montar()
    await screen.findByRole('heading', { name: 'Entrar' })

    const email = screen.getByLabelText(/E-mail/)
    const senha = screen.getByLabelText(/Senha/)
    expect(email).toHaveAttribute('type', 'email')
    expect(email).toHaveAttribute('autocomplete', 'username')
    expect(senha).toHaveAttribute('type', 'password')
    expect(senha).toHaveAttribute('autocomplete', 'current-password')
  })

  it('permite colar a senha (gerenciadores de senha)', async () => {
    const pessoa = userEvent.setup()
    montar()
    await screen.findByRole('heading', { name: 'Entrar' })

    await pessoa.click(screen.getByLabelText(/Senha/))
    await pessoa.paste('senha-colada-do-gerenciador')

    expect(screen.getByLabelText(/Senha/)).toHaveValue('senha-colada-do-gerenciador')
  })

  it('envia o e-mail sem espaços nas pontas e a senha exatamente como digitada', async () => {
    vi.mocked(api.login).mockResolvedValue({ usuario, csrf_token: 'c' })

    montar()
    await preencher('  ana@exemplo.com  ', '  senha com espaços  ')

    await waitFor(() =>
      expect(api.login).toHaveBeenCalledWith('ana@exemplo.com', '  senha com espaços  '),
    )
    expect(await screen.findByText('Página inicial')).toBeVisible()
  })

  it('pede os dois campos antes de enviar', async () => {
    montar()
    await preencher('ana@exemplo.com', '')

    expect(await screen.findByRole('alert')).toHaveTextContent('Informe o e-mail e a senha.')
    expect(api.login).not.toHaveBeenCalled()
  })

  it('mostra uma mensagem única para credenciais inválidas e não vaza o texto do servidor', async () => {
    vi.mocked(api.login).mockRejectedValue(
      new ApiError('CREDENCIAIS_INVALIDAS', 'A conta ana@exemplo.com está bloqueada', 401),
    )

    montar()
    await preencher('ana@exemplo.com', 'senha errada de teste')

    const alerta = await screen.findByRole('alert')
    expect(alerta).toHaveTextContent('E-mail ou senha inválidos.')
    expect(alerta).not.toHaveTextContent('bloqueada')
  })

  it('limpa a senha recusada, mantém o e-mail e devolve o foco à senha', async () => {
    vi.mocked(api.login).mockRejectedValue(new ApiError('CREDENCIAIS_INVALIDAS', 'x', 401))

    montar()
    await preencher('ana@exemplo.com', 'senha errada de teste')
    await screen.findByRole('alert')

    expect(screen.getByLabelText(/Senha/)).toHaveValue('')
    expect(screen.getByLabelText(/Senha/)).toHaveFocus()
    expect(screen.getByLabelText(/E-mail/)).toHaveValue('ana@exemplo.com')
  })

  it('orienta a esperar quando o limite de tentativas é atingido', async () => {
    vi.mocked(api.login).mockRejectedValue(new ApiError('LIMITE_TENTATIVAS', 'x', 429))

    montar()
    await preencher('ana@exemplo.com', 'qualquer senha longa')

    expect(await screen.findByRole('alert')).toHaveTextContent('Aguarde')
  })

  it('desabilita o botão durante o envio e impede envio duplo', async () => {
    let resolver: (valor: { usuario: typeof usuario; csrf_token: string }) => void = () => undefined
    vi.mocked(api.login).mockReturnValue(new Promise((resolve) => (resolver = resolve)))

    montar()
    await preencher('ana@exemplo.com', 'uma senha bem longa')

    const botao = await screen.findByRole('button', { name: 'Entrando…' })
    expect(botao).toBeDisabled()
    resolver({ usuario, csrf_token: 'c' })
    await screen.findByText('Página inicial')
    expect(api.login).toHaveBeenCalledTimes(1)
  })

  it('informa que a senha é redefinida pelo administrador (não há recuperação por e-mail)', async () => {
    montar()
    await screen.findByRole('heading', { name: 'Entrar' })

    expect(screen.getByText(/Peça ao administrador/)).toBeVisible()
  })

  it('não grava e-mail nem senha em localStorage ou sessionStorage', async () => {
    vi.mocked(api.login).mockRejectedValue(new ApiError('CREDENCIAIS_INVALIDAS', 'x', 401))

    montar()
    await preencher('ana@exemplo.com', 'senha-que-nao-pode-vazar')
    await screen.findByRole('alert')

    // O tema visual é a única preferência gravada; nenhum valor pode conter credenciais.
    const armazenado = [localStorage, sessionStorage]
      .flatMap((area) => Object.keys(area).map((chave) => `${chave}=${area.getItem(chave)}`))
      .join(' ')
    expect(armazenado).not.toContain('ana@exemplo.com')
    expect(armazenado).not.toContain('senha-que-nao-pode-vazar')
  })
})
