import { act, render, screen, waitFor } from '@testing-library/react'
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
import LoginPage from './LoginPage'

const CHAVE_DISPENSA = 'trapsight:convite-instalacao-dispensado'
const descritorMatchMedia = Object.getOwnPropertyDescriptor(window, 'matchMedia')
const descritorUserAgent = Object.getOwnPropertyDescriptor(navigator, 'userAgent')
const descritorLocalStorage = Object.getOwnPropertyDescriptor(window, 'localStorage')

const usuario = { troca_senha_pendente: false, papel: 'operador' as const, id: 'u1', email: 'ana@exemplo.com', nome: 'Ana' }

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
  await screen.findByRole('heading', { name: 'Entre no TrapSight' })
  if (email) await pessoa.type(screen.getByLabelText(/E-mail/), email)
  if (senha) await pessoa.type(screen.getByLabelText(/Senha/), senha)
  await pessoa.click(screen.getByRole('button', { name: 'Entrar' }))
}

function prepararCelularAndroid() {
  Object.defineProperty(navigator, 'userAgent', {
    configurable: true,
    value: 'Mozilla/5.0 (Linux; Android 15; Pixel 9) Chrome/132.0 Mobile',
  })
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: vi.fn((media: string) => ({
      matches: media === '(max-width: 767px)',
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

function restaurarDescritor(alvo: object, nome: string, descritor: PropertyDescriptor | undefined) {
  if (descritor) Object.defineProperty(alvo, nome, descritor)
  else Reflect.deleteProperty(alvo, nome)
}

beforeEach(() => {
  window.dispatchEvent(new Event('appinstalled'))
  prepararCelularAndroid()
  vi.mocked(api.getSessao).mockReset()
  vi.mocked(api.getSessao).mockRejectedValue(new ApiError('NAO_AUTENTICADO', 'x', 401))
  vi.mocked(api.login).mockReset()
})

afterEach(() => {
  window.dispatchEvent(new Event('appinstalled'))
  restaurarDescritor(window, 'matchMedia', descritorMatchMedia)
  restaurarDescritor(navigator, 'userAgent', descritorUserAgent)
  restaurarDescritor(window, 'localStorage', descritorLocalStorage)
  try {
    window.localStorage.removeItem(CHAVE_DISPENSA)
  } catch {
    // A limpeza de uma preferência de teste não deve mascarar a indisponibilidade do armazenamento.
  }
})

describe('LoginPage', () => {
  it('apresenta os campos com rótulo e os atributos de preenchimento corretos', async () => {
    montar()
    await screen.findByRole('heading', { name: 'Entre no TrapSight' })

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
    await screen.findByRole('heading', { name: 'Entre no TrapSight' })

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
    await screen.findByRole('heading', { name: 'Entre no TrapSight' })

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

  it('mantém a página de login funcional quando localStorage não está disponível', async () => {
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      get() {
        throw new DOMException('Armazenamento bloqueado', 'SecurityError')
      },
    })

    montar()
    expect(await screen.findByRole('heading', { name: 'Entre no TrapSight' })).toBeVisible()
    expect(screen.getByLabelText(/E-mail/)).toBeVisible()
  })

  it('mostra as instruções de instalação na faixa do iPhone', async () => {
    Object.defineProperty(navigator, 'userAgent', {
      configurable: true,
      value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Mobile',
    })

    montar()
    await screen.findByRole('heading', { name: 'Entre no TrapSight' })

    expect(await screen.findByRole('complementary', { name: 'Instalar o TrapSight' })).toBeVisible()
    expect(screen.getByText(/Compartilhar e depois em Adicionar à Tela de Início/)).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Instalar' })).not.toBeInTheDocument()
  })

  it('persiste a dispensa do convite de instalação e não o exibe novamente', async () => {
    const pessoa = userEvent.setup()
    const evento = Object.assign(new Event('beforeinstallprompt', { cancelable: true }), {
      platforms: ['web'],
      prompt: vi.fn().mockResolvedValue(undefined),
      userChoice: Promise.resolve({ outcome: 'dismissed' as const, platform: 'web' }),
    })

    const primeiraMontagem = montar()
    await screen.findByRole('heading', { name: 'Entre no TrapSight' })
    act(() => window.dispatchEvent(evento))
    expect(await screen.findByRole('complementary', { name: 'Instalar o TrapSight' })).toBeVisible()
    await pessoa.click(screen.getByRole('button', { name: 'Dispensar convite de instalação' }))

    expect(screen.queryByRole('complementary', { name: 'Instalar o TrapSight' })).not.toBeInTheDocument()
    expect(window.localStorage.getItem(CHAVE_DISPENSA)).toBe('true')

    primeiraMontagem.unmount()
    montar()
    await screen.findByRole('heading', { name: 'Entre no TrapSight' })
    expect(screen.queryByRole('complementary', { name: 'Instalar o TrapSight' })).not.toBeInTheDocument()
  })
})
