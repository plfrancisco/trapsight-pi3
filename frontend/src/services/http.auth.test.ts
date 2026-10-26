import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { request } from './http'
import { assinarSessaoExpirada, assinarTrocaObrigatoria, definirCsrf, limparCsrf } from './sessao'

const fetchSimulado = vi.fn()

it('propaga troca obrigatória recebida da API', async () => {
  const ouvinte = vi.fn()
  const cancelar = assinarTrocaObrigatoria(ouvinte)
  fetchSimulado.mockResolvedValue(erroDaApi('TROCA_DE_SENHA_OBRIGATORIA', 403))
  try {
    await expect(request('armadilhas')).rejects.toMatchObject({
      codigo: 'TROCA_DE_SENHA_OBRIGATORIA',
    })
    expect(ouvinte).toHaveBeenCalledTimes(1)
  } finally {
    cancelar()
  }
})

function resposta(status: number, corpo: unknown = ''): Response {
  const texto = typeof corpo === 'string' ? corpo : JSON.stringify(corpo)
  return { ok: status < 400, status, text: async () => texto } as Response
}

function erroDaApi(codigo: string, status: number) {
  return resposta(status, { erro: { codigo, mensagem: 'texto' } })
}

function ultimaChamada(): RequestInit {
  return fetchSimulado.mock.calls[fetchSimulado.mock.calls.length - 1][1] as RequestInit
}

beforeEach(() => {
  fetchSimulado.mockReset()
  vi.stubGlobal('fetch', fetchSimulado)
})

afterEach(() => {
  limparCsrf()
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
  vi.resetModules()
})

describe('token CSRF', () => {
  it.each(['POST', 'PATCH', 'PUT', 'DELETE'])('envia X-CSRF-Token em %s', async (metodo) => {
    definirCsrf('csrf-abc')
    fetchSimulado.mockResolvedValue(resposta(200, {}))

    await request('armadilhas', { method: metodo, body: {} })

    expect((ultimaChamada().headers as Record<string, string>)['X-CSRF-Token']).toBe('csrf-abc')
  })

  it.each(['GET', 'HEAD'])('não envia o token em %s', async (metodo) => {
    definirCsrf('csrf-abc')
    fetchSimulado.mockResolvedValue(resposta(200, {}))

    await request('armadilhas', { method: metodo })

    expect(ultimaChamada().headers as Record<string, string>).not.toHaveProperty('X-CSRF-Token')
  })

  it('não inventa um token quando não há sessão', async () => {
    fetchSimulado.mockResolvedValue(resposta(200, {}))

    await request('auth/login', { method: 'POST', body: {} })

    expect(ultimaChamada().headers as Record<string, string>).not.toHaveProperty('X-CSRF-Token')
  })

  it('usa o método em maiúsculas ao decidir sobre o token', async () => {
    definirCsrf('csrf-abc')
    fetchSimulado.mockResolvedValue(resposta(200, {}))

    await request('armadilhas', { method: 'post', body: {} })

    expect((ultimaChamada().headers as Record<string, string>)['X-CSRF-Token']).toBe('csrf-abc')
    expect(ultimaChamada().method).toBe('POST')
  })
})

describe('credenciais', () => {
  it('envia o cookie quando a API está em outra origem (desenvolvimento)', async () => {
    fetchSimulado.mockResolvedValue(resposta(200, {}))

    await request('armadilhas')

    expect(ultimaChamada().credentials).toBe('include')
  })

  it('usa a mesma origem e o endereço relativo quando VITE_API_URL é /api', async () => {
    vi.stubEnv('VITE_API_URL', '/api')
    vi.resetModules()
    const { request: requestRelativo } = await import('./http')
    fetchSimulado.mockResolvedValue(resposta(200, {}))

    await requestRelativo('armadilhas')

    expect(ultimaChamada().credentials).toBe('same-origin')
    expect(fetchSimulado.mock.calls[0][0]).toBe(`${window.location.origin}/api/armadilhas`)
  })
})

describe('sessão expirada', () => {
  it('avisa os ouvintes quando a API responde NAO_AUTENTICADO', async () => {
    const ouvinte = vi.fn()
    const cancelar = assinarSessaoExpirada(ouvinte)
    fetchSimulado.mockResolvedValue(erroDaApi('NAO_AUTENTICADO', 401))

    await expect(request('armadilhas')).rejects.toMatchObject({ codigo: 'NAO_AUTENTICADO' })

    expect(ouvinte).toHaveBeenCalledTimes(1)
    cancelar()
  })

  it.each([
    ['CREDENCIAIS_INVALIDAS', 401],
    ['CSRF_INVALIDO', 403],
    ['ARMADILHA_NAO_ENCONTRADA', 404],
    ['LIMITE_TENTATIVAS', 429],
  ])('não avisa para %s', async (codigo, status) => {
    const ouvinte = vi.fn()
    const cancelar = assinarSessaoExpirada(ouvinte)
    fetchSimulado.mockResolvedValue(erroDaApi(codigo, status))

    await expect(request('armadilhas')).rejects.toMatchObject({ codigo })

    expect(ouvinte).not.toHaveBeenCalled()
    cancelar()
  })

  it('não repete a requisição ao receber 401 (sem laço)', async () => {
    fetchSimulado.mockResolvedValue(erroDaApi('NAO_AUTENTICADO', 401))

    await expect(request('armadilhas')).rejects.toBeDefined()

    expect(fetchSimulado).toHaveBeenCalledTimes(1)
  })
})

describe('resposta sem corpo', () => {
  it('aceita 204 (logout) sem tentar interpretar JSON', async () => {
    fetchSimulado.mockResolvedValue(resposta(204, ''))

    await expect(request<void>('auth/logout', { method: 'POST' })).resolves.toBeUndefined()
  })

  it('continua recusando JSON inválido numa resposta 200 com corpo', async () => {
    fetchSimulado.mockResolvedValue(resposta(200, '{quebrado'))

    await expect(request('armadilhas')).rejects.toMatchObject({ codigo: 'RESPOSTA_INVALIDA' })
  })
})
