import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from './erros'
import { request } from './http'

const fetchSimulado = vi.fn()

beforeEach(() => {
  fetchSimulado.mockReset()
  vi.stubGlobal('fetch', fetchSimulado)
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('request', () => {
  it('converte o envelope de erro da API para ApiError', async () => {
    fetchSimulado.mockResolvedValue(
      ({
        ok: false,
        status: 409,
        text: async () =>
          JSON.stringify({
          erro: {
            codigo: 'REFIL_ATIVO_INEXISTENTE',
            mensagem: 'A armadilha não possui refil ativo.',
            detalhes: { armadilha_id: 'arm-1' },
          },
        }),
      }) as Response,
    )

    await expect(request('analises')).rejects.toMatchObject({
      codigo: 'REFIL_ATIVO_INEXISTENTE',
      mensagem: 'A armadilha não possui refil ativo.',
      detalhes: { armadilha_id: 'arm-1' },
      status: 409,
    })
  })

  it('marca como inválido um envelope de erro fora do formato', async () => {
    fetchSimulado.mockResolvedValue(
      ({
        ok: false,
        status: 500,
        text: async () => JSON.stringify({ mensagem: 'falha sem envelope' }),
      }) as Response,
    )

    await expect(request('analises')).rejects.toMatchObject({
      codigo: 'RESPOSTA_INVALIDA',
      status: 500,
    })
  })

  it('marca como inválido um corpo JSON malformado de sucesso', async () => {
    fetchSimulado.mockResolvedValue({
      ok: true,
      status: 200,
      text: async () => 'não é JSON',
    } as Response)

    await expect(request('armadilhas')).rejects.toMatchObject({
      codigo: 'RESPOSTA_INVALIDA',
      status: 200,
    })
  })

  it('classifica falha de transporte sem usar o texto do erro', async () => {
    fetchSimulado.mockRejectedValue(new TypeError('mensagem variável do navegador'))

    const falha = request('armadilhas')

    await expect(falha).rejects.toBeInstanceOf(ApiError)
    await expect(falha).rejects.toMatchObject({
      codigo: 'FALHA_DE_REDE',
      status: 0,
    })
  })

  it('aplica o timeout padrão e o representa por código estável', async () => {
    vi.useFakeTimers()
    fetchSimulado.mockImplementation(
      (_url: RequestInfo | URL, init?: RequestInit) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener(
            'abort',
            () => reject(new DOMException('Cancelada', 'AbortError')),
            { once: true },
          )
        }),
    )

    const rejeicao = expect(request('armadilhas')).rejects.toMatchObject({
      codigo: 'TEMPO_ESGOTADO',
      status: 0,
    })
    await vi.advanceTimersByTimeAsync(15_000)
    await rejeicao
  })

  it('encaminha o AbortSignal e preserva o cancelamento externo', async () => {
    const controlador = new AbortController()
    fetchSimulado.mockImplementation(
      (_url: RequestInfo | URL, init?: RequestInit) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener(
            'abort',
            () => reject(new DOMException('Cancelada', 'AbortError')),
            { once: true },
          )
        }),
    )

    const pendente = request('armadilhas', { signal: controlador.signal })
    controlador.abort()

    await expect(pendente).rejects.toMatchObject({ name: 'AbortError' })
  })
})
