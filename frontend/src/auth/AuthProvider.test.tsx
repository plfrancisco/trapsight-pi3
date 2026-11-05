import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../services/auth', () => ({
  login: vi.fn(),
  logout: vi.fn(),
  getSessao: vi.fn(),
  changeSenha: vi.fn(),
}))

import { CHAVE_ATIVIDADE, CHAVE_SESSAO, gravarCache, lerCache } from '../lib/cacheLocal'
import { registrarAtividade } from '../lib/inatividade'
import * as api from '../services/auth'
import { ApiError } from '../services/erros'
import { limparCsrf, notificarSessaoExpirada, obterCsrf } from '../services/sessao'
import AuthProvider from './AuthProvider'
import { useAuth } from './useAuth'

const usuario = { troca_senha_pendente: false, papel: 'operador' as const, id: 'u1', email: 'ana@exemplo.com', nome: 'Ana' }

function Sonda() {
  const auth = useAuth()
  return (
    <div>
      <p data-testid="estado">{auth.estado}</p>
      <p data-testid="usuario">{auth.usuario?.email ?? 'ninguem'}</p>
      <p data-testid="motivo">{auth.motivoSaida ?? 'nenhum'}</p>
      <button onClick={() => void auth.login('ana@exemplo.com', 'senha longa o bastante').catch(() => undefined)} type="button">
        entrar
      </button>
      <button onClick={() => void auth.logout().catch(() => undefined)} type="button">
        sair
      </button>
      <button onClick={() => void auth.changeSenha('atual', 'nova senha bem longa')} type="button">
        trocar
      </button>
      <button onClick={auth.recarregarSessao} type="button">
        recarregar
      </button>
    </div>
  )
}

const montar = (ativa = true) =>
  render(
    <AuthProvider ativa={ativa}>
      <Sonda />
    </AuthProvider>,
  )

const estado = () => screen.getByTestId('estado').textContent

beforeEach(() => {
  vi.mocked(api.getSessao).mockReset()
  vi.mocked(api.login).mockReset()
  vi.mocked(api.logout).mockReset()
  vi.mocked(api.changeSenha).mockReset()
})

afterEach(() => {
  limparCsrf()
})

describe('AuthProvider', () => {
  it('recupera a sessão ao abrir e guarda o token CSRF em memória', async () => {
    vi.mocked(api.getSessao).mockResolvedValue({ usuario, csrf_token: 'csrf-1' })

    montar()
    expect(estado()).toBe('carregando')

    await waitFor(() => expect(estado()).toBe('autenticado'))
    expect(screen.getByTestId('usuario')).toHaveTextContent('ana@exemplo.com')
    expect(obterCsrf()).toBe('csrf-1')
  })

  it('fica anônimo, sem aviso de expiração, quando não há sessão ao abrir', async () => {
    vi.mocked(api.getSessao).mockRejectedValue(new ApiError('NAO_AUTENTICADO', 'x', 401))

    montar()

    await waitFor(() => expect(estado()).toBe('anonimo'))
    expect(screen.getByTestId('motivo')).toHaveTextContent('nenhum')
    expect(obterCsrf()).toBeNull()
  })

  it('indica erro (e não anônimo) quando a API está fora do ar', async () => {
    vi.mocked(api.getSessao).mockRejectedValue(new ApiError('FALHA_DE_REDE', 'x', 0))

    montar()

    await waitFor(() => expect(estado()).toBe('erro'))
  })

  it('tenta de novo ao pedir para recarregar a sessão', async () => {
    vi.mocked(api.getSessao).mockRejectedValueOnce(new ApiError('FALHA_DE_REDE', 'x', 0))
    vi.mocked(api.getSessao).mockResolvedValueOnce({ usuario, csrf_token: 'csrf-2' })
    const usuarioEvento = userEvent.setup()

    montar()
    await waitFor(() => expect(estado()).toBe('erro'))
    await usuarioEvento.click(screen.getByRole('button', { name: 'recarregar' }))

    await waitFor(() => expect(estado()).toBe('autenticado'))
    expect(api.getSessao).toHaveBeenCalledTimes(2)
  })

  it('autentica no login e guarda o novo token CSRF', async () => {
    vi.mocked(api.getSessao).mockRejectedValue(new ApiError('NAO_AUTENTICADO', 'x', 401))
    vi.mocked(api.login).mockResolvedValue({ usuario, csrf_token: 'csrf-login' })
    const usuarioEvento = userEvent.setup()

    montar()
    await waitFor(() => expect(estado()).toBe('anonimo'))
    await usuarioEvento.click(screen.getByRole('button', { name: 'entrar' }))

    await waitFor(() => expect(estado()).toBe('autenticado'))
    expect(obterCsrf()).toBe('csrf-login')
  })

  it('permanece anônimo quando o login falha', async () => {
    vi.mocked(api.getSessao).mockRejectedValue(new ApiError('NAO_AUTENTICADO', 'x', 401))
    vi.mocked(api.login).mockRejectedValue(new ApiError('CREDENCIAIS_INVALIDAS', 'x', 401))
    const usuarioEvento = userEvent.setup()

    montar()
    await waitFor(() => expect(estado()).toBe('anonimo'))
    await usuarioEvento.click(screen.getByRole('button', { name: 'entrar' }))

    await waitFor(() => expect(api.login).toHaveBeenCalled())
    expect(estado()).toBe('anonimo')
    expect(obterCsrf()).toBeNull()
  })

  it('sai no servidor, esquece o token e registra que o usuário saiu', async () => {
    vi.mocked(api.getSessao).mockResolvedValue({ usuario, csrf_token: 'csrf-1' })
    vi.mocked(api.logout).mockResolvedValue(undefined)
    const usuarioEvento = userEvent.setup()

    montar()
    await waitFor(() => expect(estado()).toBe('autenticado'))
    await usuarioEvento.click(screen.getByRole('button', { name: 'sair' }))

    await waitFor(() => expect(estado()).toBe('anonimo'))
    expect(api.logout).toHaveBeenCalledTimes(1)
    expect(obterCsrf()).toBeNull()
    expect(screen.getByTestId('motivo')).toHaveTextContent('saiu')
  })

  it('NÃO se considera fora quando o logout falha no servidor', async () => {
    vi.mocked(api.getSessao).mockResolvedValue({ usuario, csrf_token: 'csrf-1' })
    vi.mocked(api.logout).mockRejectedValue(new ApiError('FALHA_DE_REDE', 'x', 0))
    const usuarioEvento = userEvent.setup()

    montar()
    await waitFor(() => expect(estado()).toBe('autenticado'))
    await usuarioEvento.click(screen.getByRole('button', { name: 'sair' }))

    await waitFor(() => expect(api.logout).toHaveBeenCalled())
    expect(estado()).toBe('autenticado')
    expect(obterCsrf()).toBe('csrf-1')
  })

  it('considera o logout concluído se a sessão já não existia no servidor', async () => {
    vi.mocked(api.getSessao).mockResolvedValue({ usuario, csrf_token: 'csrf-1' })
    vi.mocked(api.logout).mockRejectedValue(new ApiError('NAO_AUTENTICADO', 'x', 401))
    const usuarioEvento = userEvent.setup()

    montar()
    await waitFor(() => expect(estado()).toBe('autenticado'))
    await usuarioEvento.click(screen.getByRole('button', { name: 'sair' }))

    await waitFor(() => expect(estado()).toBe('anonimo'))
  })

  it('encerra a sessão local quando a API avisa que ela expirou', async () => {
    vi.mocked(api.getSessao).mockResolvedValue({ usuario, csrf_token: 'csrf-1' })

    montar()
    await waitFor(() => expect(estado()).toBe('autenticado'))
    act(() => notificarSessaoExpirada())

    await waitFor(() => expect(estado()).toBe('anonimo'))
    expect(screen.getByTestId('motivo')).toHaveTextContent('expirou')
    expect(obterCsrf()).toBeNull()
  })

  it('ignora o aviso de expiração quando ninguém estava autenticado', async () => {
    vi.mocked(api.getSessao).mockRejectedValue(new ApiError('NAO_AUTENTICADO', 'x', 401))

    montar()
    await waitFor(() => expect(estado()).toBe('anonimo'))
    act(() => notificarSessaoExpirada())

    expect(screen.getByTestId('motivo')).toHaveTextContent('nenhum')
  })

  it('renova o token CSRF depois de trocar a senha', async () => {
    vi.mocked(api.getSessao).mockResolvedValue({ usuario, csrf_token: 'csrf-antigo' })
    vi.mocked(api.changeSenha).mockResolvedValue({ csrf_token: 'csrf-novo' })
    const usuarioEvento = userEvent.setup()

    montar()
    await waitFor(() => expect(estado()).toBe('autenticado'))
    await usuarioEvento.click(screen.getByRole('button', { name: 'trocar' }))

    await waitFor(() => expect(obterCsrf()).toBe('csrf-novo'))
  })

  it('pede nova verificação se a senha mudou mas consultar a sessão falhou', async () => {
    vi.mocked(api.getSessao)
      .mockResolvedValueOnce({ usuario, csrf_token: 'csrf-antigo' })
      .mockRejectedValue(new ApiError('FALHA_DE_REDE', 'x', 0))
    vi.mocked(api.changeSenha).mockResolvedValue({ csrf_token: 'csrf-novo' })
    montar()
    await waitFor(() => expect(estado()).toBe('autenticado'))
    await userEvent.click(screen.getByRole('button', { name: 'trocar' }))
    await waitFor(() => expect(estado()).toBe('erro'))
    expect(api.changeSenha).toHaveBeenCalledTimes(1)
    expect(obterCsrf()).toBe('csrf-novo')
  })

  it('não consulta a API e já se considera autenticado com a autenticação desligada', () => {
    montar(false)

    expect(estado()).toBe('autenticado')
    expect(api.getSessao).not.toHaveBeenCalled()
  })

  it('só guarda no aparelho id, nome e papel: nunca CSRF, e-mail nem sessionStorage', async () => {
    vi.mocked(api.getSessao).mockResolvedValue({ usuario, csrf_token: 'csrf-secreto' })

    montar()
    await waitFor(() => expect(estado()).toBe('autenticado'))

    const guardado = Object.keys(localStorage).map((chave) => `${chave}=${localStorage.getItem(chave)}`).join('\n')
    expect(guardado).toContain('"nome":"Ana"')
    expect(guardado).not.toContain('csrf-secreto')
    expect(guardado).not.toContain('ana@exemplo.com')
    expect(sessionStorage.length).toBe(0)
  })
})

describe('AuthProvider: cache local e inatividade', () => {
  const dica = { id: 'u1', nome: 'Ana', papel: 'operador' as const }

  it('abre já autenticado pela dica guardada e confirma a sessão em seguida', async () => {
    gravarCache(CHAVE_SESSAO, dica)
    registrarAtividade()
    vi.mocked(api.getSessao).mockResolvedValue({ usuario, csrf_token: 'csrf-3' })

    montar()
    expect(estado()).toBe('autenticado')
    expect(screen.getByTestId('usuario')).toHaveTextContent('')

    await waitFor(() => expect(screen.getByTestId('usuario')).toHaveTextContent('ana@exemplo.com'))
    expect(obterCsrf()).toBe('csrf-3')
  })

  it('volta ao login, avisando a expiração, se o servidor não reconhece a sessão guardada', async () => {
    gravarCache(CHAVE_SESSAO, dica)
    registrarAtividade()
    vi.mocked(api.getSessao).mockRejectedValue(new ApiError('NAO_AUTENTICADO', 'x', 401))

    montar()
    expect(estado()).toBe('autenticado')

    await waitFor(() => expect(estado()).toBe('anonimo'))
    expect(screen.getByTestId('motivo')).toHaveTextContent('expirou')
    expect(lerCache(CHAVE_SESSAO)).toBeNull()
  })

  it('continua vendo o que já tinha quando está sem rede ao abrir', async () => {
    gravarCache(CHAVE_SESSAO, dica)
    registrarAtividade()
    vi.mocked(api.getSessao).mockRejectedValue(new ApiError('FALHA_DE_REDE', 'x', 0))

    montar()
    await waitFor(() => expect(api.getSessao).toHaveBeenCalled())
    await new Promise((resolver) => setTimeout(resolver, 20))

    expect(estado()).toBe('autenticado')
  })

  it('reaberto depois de 20 minutos parado, sai sozinho, revoga a sessão e apaga o cache', async () => {
    gravarCache(CHAVE_SESSAO, dica)
    gravarCache('armadilhas', [{ id: 'a1' }])
    registrarAtividade(Date.now() - 21 * 60_000)
    vi.mocked(api.getSessao).mockResolvedValue({ usuario, csrf_token: 'csrf-4' })
    vi.mocked(api.logout).mockResolvedValue(undefined)

    montar()

    expect(estado()).toBe('anonimo')
    expect(screen.getByTestId('motivo')).toHaveTextContent('inativo')
    await waitFor(() => expect(api.logout).toHaveBeenCalledTimes(1))
    expect(lerCache(CHAVE_SESSAO)).toBeNull()
    expect(lerCache('armadilhas')).toBeNull()
    expect(estado()).toBe('anonimo')
  })

  it('com o app aberto, sai sozinho aos 20 minutos sem uso e apaga o cache', async () => {
    vi.mocked(api.getSessao).mockResolvedValue({ usuario, csrf_token: 'csrf-5' })
    vi.mocked(api.logout).mockResolvedValue(undefined)
    montar()
    await waitFor(() => expect(estado()).toBe('autenticado'))
    await waitFor(() => expect(lerCache(CHAVE_SESSAO)).not.toBeNull())

    localStorage.setItem(CHAVE_ATIVIDADE, String(Date.now() - 21 * 60_000))
    act(() => document.dispatchEvent(new Event('visibilitychange')))

    await waitFor(() => expect(estado()).toBe('anonimo'))
    expect(screen.getByTestId('motivo')).toHaveTextContent('inativo')
    expect(api.logout).toHaveBeenCalledTimes(1)
    expect(lerCache(CHAVE_SESSAO)).toBeNull()
    expect(obterCsrf()).toBeNull()
  })

  it('apaga o cache ao sair e quando o servidor responde que a sessão acabou', async () => {
    vi.mocked(api.getSessao).mockResolvedValue({ usuario, csrf_token: 'csrf-6' })
    vi.mocked(api.logout).mockResolvedValue(undefined)
    const usuarioEvento = userEvent.setup()
    montar()
    await waitFor(() => expect(lerCache(CHAVE_SESSAO)).not.toBeNull())
    gravarCache('armadilhas', [{ id: 'a1' }])

    await usuarioEvento.click(screen.getByRole('button', { name: 'sair' }))

    await waitFor(() => expect(estado()).toBe('anonimo'))
    expect(lerCache(CHAVE_SESSAO)).toBeNull()
    expect(lerCache('armadilhas')).toBeNull()
  })

  it('apaga o cache de outra conta ao entrar', async () => {
    gravarCache('armadilhas', [{ id: 'da-outra-conta' }])
    vi.mocked(api.getSessao).mockRejectedValue(new ApiError('NAO_AUTENTICADO', 'x', 401))
    vi.mocked(api.login).mockResolvedValue({ usuario, csrf_token: 'csrf-7' })
    const usuarioEvento = userEvent.setup()
    montar()
    await waitFor(() => expect(estado()).toBe('anonimo'))
    gravarCache('armadilhas', [{ id: 'da-outra-conta' }])

    await usuarioEvento.click(screen.getByRole('button', { name: 'entrar' }))

    await waitFor(() => expect(estado()).toBe('autenticado'))
    expect(lerCache('armadilhas')).toBeNull()
  })
})
