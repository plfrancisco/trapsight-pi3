import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('./http', () => ({ request: vi.fn() }))

import { changeSenha, getSessao, login, logout } from './auth'
import { request } from './http'

const requestSimulado = vi.mocked(request)

beforeEach(() => {
  requestSimulado.mockReset()
  requestSimulado.mockResolvedValue(undefined)
})

describe('serviços de autenticação', () => {
  it('login envia e-mail e senha em POST auth/login', async () => {
    await login('ana@exemplo.com', 'uma senha bem longa')

    expect(requestSimulado).toHaveBeenCalledWith('auth/login', {
      method: 'POST',
      body: { email: 'ana@exemplo.com', senha: 'uma senha bem longa' },
      signal: undefined,
    })
  })

  it('logout usa POST auth/logout sem corpo', async () => {
    await logout()

    expect(requestSimulado).toHaveBeenCalledWith('auth/logout', { method: 'POST', signal: undefined })
  })

  it('getSessao consulta GET auth/me', async () => {
    const controlador = new AbortController()

    await getSessao(controlador.signal)

    expect(requestSimulado).toHaveBeenCalledWith('auth/me', { signal: controlador.signal })
  })

  it('changeSenha envia os campos no formato da API', async () => {
    await changeSenha('atual-antiga-123456', 'nova-senha-bem-longa')

    expect(requestSimulado).toHaveBeenCalledWith('auth/senha', {
      method: 'POST',
      body: { senha_atual: 'atual-antiga-123456', senha_nova: 'nova-senha-bem-longa' },
      signal: undefined,
    })
  })
})
