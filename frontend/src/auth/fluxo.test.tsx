import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../services/auth', () => ({
  login: vi.fn(),
  logout: vi.fn(),
  getSessao: vi.fn(),
  changeSenha: vi.fn(),
}))
vi.mock('../services/armadilhas', () => ({
  listArmadilhas: vi.fn(),
  getArmadilha: vi.fn(),
  createArmadilha: vi.fn(),
  updateArmadilha: vi.fn(),
  replaceRefil: vi.fn(),
}))
vi.mock('../services/analises', () => ({
  listAnalises: vi.fn(),
  createAnalise: vi.fn(),
  getAnalise: vi.fn(),
}))
vi.mock('../services/usuarios', () => ({
  listUsuarios: vi.fn().mockResolvedValue([]),
  createUsuario: vi.fn(),
  mensagemDeContas: vi.fn(),
}))

import { Rotas } from '../App'
import * as api from '../services/auth'
import { listArmadilhas } from '../services/armadilhas'
import { listUsuarios } from '../services/usuarios'
import { ApiError } from '../services/erros'
import { limparCsrf, notificarSessaoExpirada, notificarTrocaObrigatoria } from '../services/sessao'
import AuthProvider from './AuthProvider'

const usuario = { troca_senha_pendente: false, papel: 'operador' as const, id: 'u1', email: 'ana@exemplo.com', nome: 'Ana' }

function Local() {
  const { pathname, search } = useLocation()
  return <p data-testid="local">{pathname + search}</p>
}

const montar = (caminho: string) =>
  render(
    <MemoryRouter initialEntries={[caminho]}>
      <AuthProvider ativa>
        <Rotas />
        <Local />
      </AuthProvider>
    </MemoryRouter>,
  )

const local = () => screen.getByTestId('local').textContent

beforeEach(() => {
  vi.mocked(listUsuarios).mockClear()
  vi.mocked(api.getSessao).mockReset()
  vi.mocked(api.login).mockReset()
  vi.mocked(api.logout).mockReset()
  vi.mocked(listArmadilhas).mockReset()
  vi.mocked(listArmadilhas).mockResolvedValue([])
})

afterEach(() => limparCsrf())

describe('fluxo de acesso', () => {
  it('reage à exigência de troca recebida durante a navegação', async () => {
    vi.mocked(api.getSessao).mockResolvedValue({ usuario, csrf_token: 'c' })
    montar('/')
    await screen.findByRole('heading', { name: 'Dashboard', level: 1 })
    act(() => notificarTrocaObrigatoria())
    expect(await screen.findByRole('heading', { name: 'Alterar senha', level: 1 })).toBeVisible()
    expect(local()).toBe('/conta/senha')
  })

  it('encaminha gerente pendente para trocar senha antes de montar Contas', async () => {
    vi.mocked(api.getSessao).mockResolvedValue({
      usuario: { ...usuario, papel: 'gerente', troca_senha_pendente: true }, csrf_token: 'c',
    })
    montar('/contas')
    expect(await screen.findByRole('heading', { name: 'Alterar senha', level: 1 })).toBeVisible()
    expect(local()).toBe('/conta/senha')
    expect(screen.getByText(/substitua a senha inicial/)).toBeVisible()
    expect(listUsuarios).not.toHaveBeenCalled()
    expect(listArmadilhas).not.toHaveBeenCalled()
  })

  it('recupera a flag do servidor depois da troca e libera o painel', async () => {
    vi.mocked(api.getSessao).mockResolvedValueOnce({
      usuario: { ...usuario, troca_senha_pendente: true }, csrf_token: 'antigo',
    }).mockResolvedValue({ usuario, csrf_token: 'novo' })
    vi.mocked(api.changeSenha).mockResolvedValue({ csrf_token: 'novo' })
    montar('/')
    await screen.findByRole('heading', { name: 'Alterar senha', level: 1 })
    const pessoa = userEvent.setup()
    await pessoa.type(screen.getByLabelText(/^Senha atual/), 'uma frase longa e segura')
    await pessoa.type(screen.getByLabelText(/^Nova senha/), 'outra frase longa e segura')
    await pessoa.type(screen.getByLabelText(/^Confirmar nova senha/), 'outra frase longa e segura')
    await pessoa.click(screen.getByRole('button', { name: 'Alterar senha' }))
    expect(await screen.findByText(/Senha alterada/)).toBeVisible()
    expect(screen.queryByText(/substitua a senha inicial/)).not.toBeInTheDocument()
    await pessoa.click(screen.getByRole('link', { name: 'Voltar ao painel' }))
    expect(await screen.findByRole('heading', { name: 'Dashboard', level: 1 })).toBeVisible()
    expect(api.getSessao).toHaveBeenCalledTimes(2)
  })

  it('mantém logout disponível durante a troca pendente', async () => {
    vi.mocked(api.getSessao).mockResolvedValue({
      usuario: { ...usuario, troca_senha_pendente: true }, csrf_token: 'c',
    })
    vi.mocked(api.logout).mockResolvedValue(undefined)
    montar('/')
    await screen.findByRole('heading', { name: 'Alterar senha', level: 1 })
    await userEvent.click(screen.getByRole('button', { name: 'Sair' }))
    expect(await screen.findByRole('heading', { name: 'Entrar', level: 1 })).toBeVisible()
  })

  it('recusa URL de Contas ao operador sem carregar contas', async () => {
    vi.mocked(api.getSessao).mockResolvedValue({ usuario, csrf_token: 'c' })
    montar('/contas')
    expect(await screen.findByRole('alert')).toHaveTextContent('Acesso negado')
    expect(screen.queryByRole('heading', { name: 'Contas' })).not.toBeInTheDocument()
    expect(listUsuarios).not.toHaveBeenCalled()
  })

  it('abre Contas pelo acesso direto do gerente', async () => {
    vi.mocked(api.getSessao).mockResolvedValue({
      usuario: { ...usuario, papel: 'gerente' }, csrf_token: 'c',
    })
    montar('/contas')
    expect(await screen.findByRole('heading', { name: 'Contas', level: 1 })).toBeVisible()
    expect(await screen.findByText('Nenhuma conta cadastrada.')).toBeVisible()
  })

  it('leva ao login quem não tem sessão e não exibe nada protegido', async () => {
    vi.mocked(api.getSessao).mockRejectedValue(new ApiError('NAO_AUTENTICADO', 'x', 401))

    montar('/armadilhas/arm-1?aba=grafico')

    expect(await screen.findByRole('heading', { name: 'Entrar', level: 1 })).toBeVisible()
    expect(local()).toBe('/login')
    expect(screen.queryByRole('heading', { name: 'Detalhe da armadilha' })).not.toBeInTheDocument()
    expect(listArmadilhas).not.toHaveBeenCalled()
  })

  it('não mostra conteúdo protegido enquanto verifica a sessão', async () => {
    let resolver: (valor: { usuario: typeof usuario; csrf_token: string }) => void = () => undefined
    vi.mocked(api.getSessao).mockReturnValue(new Promise((resolve) => (resolver = resolve)))

    montar('/')

    expect(screen.getByRole('status')).toHaveTextContent('Carregando')
    expect(screen.queryByRole('heading', { name: 'Dashboard' })).not.toBeInTheDocument()
    expect(local()).toBe('/')

    await act(async () => resolver({ usuario, csrf_token: 'c' }))
    expect(await screen.findByRole('heading', { name: 'Dashboard', level: 1 })).toBeVisible()
  })

  it('depois de entrar volta ao destino original, incluindo a consulta', async () => {
    vi.mocked(api.getSessao).mockRejectedValue(new ApiError('NAO_AUTENTICADO', 'x', 401))
    vi.mocked(api.login).mockResolvedValue({ usuario, csrf_token: 'c' })
    const pessoa = userEvent.setup()

    montar('/analises/nova?armadilha=arm-1')
    await screen.findByRole('heading', { name: 'Entrar' })
    await pessoa.type(screen.getByLabelText(/E-mail/), 'ana@exemplo.com')
    await pessoa.type(screen.getByLabelText(/Senha/), 'uma senha bem longa')
    await pessoa.click(screen.getByRole('button', { name: 'Entrar' }))

    await waitFor(() => expect(local()).toBe('/analises/nova?armadilha=arm-1'))
    expect(await screen.findByRole('heading', { name: 'Nova análise', level: 1 })).toBeVisible()
  })

  it('quem já tem sessão e abre /login é levado ao início', async () => {
    vi.mocked(api.getSessao).mockResolvedValue({ usuario, csrf_token: 'c' })

    montar('/login')

    expect(await screen.findByRole('heading', { name: 'Dashboard', level: 1 })).toBeVisible()
    expect(local()).toBe('/')
  })

  it('a página 404 também fica atrás do login (não revela rotas)', async () => {
    vi.mocked(api.getSessao).mockRejectedValue(new ApiError('NAO_AUTENTICADO', 'x', 401))

    montar('/rota-que-nao-existe')

    expect(await screen.findByRole('heading', { name: 'Entrar' })).toBeVisible()
    expect(screen.queryByText('Página não encontrada')).not.toBeInTheDocument()
  })

  it('sessão expirada no meio do uso volta ao login com aviso e retorna depois', async () => {
    vi.mocked(api.getSessao).mockResolvedValue({ usuario, csrf_token: 'c' })

    montar('/analises/nova')
    await screen.findByRole('heading', { name: 'Nova análise', level: 1 })
    act(() => notificarSessaoExpirada())

    expect(await screen.findByRole('heading', { name: 'Entrar' })).toBeVisible()
    expect(screen.getByRole('status')).toHaveTextContent('Sua sessão expirou. Entre novamente.')
    expect(local()).toBe('/login')
  })

  it('sair leva ao login SEM aviso de expiração', async () => {
    vi.mocked(api.getSessao).mockResolvedValue({ usuario, csrf_token: 'c' })
    vi.mocked(api.logout).mockResolvedValue(undefined)
    const pessoa = userEvent.setup()

    montar('/')
    await screen.findByRole('heading', { name: 'Dashboard', level: 1 })
    await pessoa.click(screen.getByRole('button', { name: 'Sair' }))

    expect(await screen.findByRole('heading', { name: 'Entrar' })).toBeVisible()
    expect(screen.queryByText(/expirou/)).not.toBeInTheDocument()
  })

  it('depois de sair e entrar de novo, vai ao início e não à página anterior', async () => {
    vi.mocked(api.getSessao).mockResolvedValue({ usuario, csrf_token: 'c' })
    vi.mocked(api.logout).mockResolvedValue(undefined)
    vi.mocked(api.login).mockResolvedValue({ usuario, csrf_token: 'c2' })
    const pessoa = userEvent.setup()

    montar('/analises/nova')
    await screen.findByRole('heading', { name: 'Nova análise', level: 1 })
    await pessoa.click(screen.getByRole('button', { name: 'Sair' }))
    await screen.findByRole('heading', { name: 'Entrar' })
    await pessoa.type(screen.getByLabelText(/E-mail/), 'ana@exemplo.com')
    await pessoa.type(screen.getByLabelText(/Senha/), 'uma senha bem longa')
    await pessoa.click(screen.getByRole('button', { name: 'Entrar' }))

    await waitFor(() => expect(local()).toBe('/'))
  })

  it('oferece nova tentativa quando não consegue verificar a sessão', async () => {
    vi.mocked(api.getSessao).mockRejectedValueOnce(new ApiError('FALHA_DE_REDE', 'x', 0))
    vi.mocked(api.getSessao).mockResolvedValueOnce({ usuario, csrf_token: 'c' })
    const pessoa = userEvent.setup()

    montar('/')
    expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível verificar sua sessão')
    await pessoa.click(screen.getByRole('button', { name: 'Tentar novamente' }))

    expect(await screen.findByRole('heading', { name: 'Dashboard', level: 1 })).toBeVisible()
  })

  it('um destino malicioso no estado de navegação é ignorado (sem open redirect)', async () => {
    vi.mocked(api.getSessao).mockResolvedValue({ usuario, csrf_token: 'c' })
    const original = window.location.href

    render(
      <MemoryRouter initialEntries={[{ pathname: '/login', state: { destino: 'https://invasor.example' } }]}>
        <AuthProvider ativa>
          <Rotas />
          <Local />
        </AuthProvider>
      </MemoryRouter>,
    )

    await waitFor(() => expect(local()).toBe('/'))
    expect(window.location.href).toBe(original)
  })
})
