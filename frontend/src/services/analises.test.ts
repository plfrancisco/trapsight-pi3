import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { API_URL } from '../config'
import { createAnalise, getAnalise, listAnalises } from './analises'

const respostaJson = (dados: unknown, status = 200) =>
  ({
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(dados),
  }) as Response

const fetchSimulado = vi.fn()
const urlDaApi = (caminho: string) =>
  new URL(caminho, API_URL.replace(/\/+$/, '') + '/').toString()

beforeEach(() => {
  fetchSimulado.mockReset()
  vi.stubGlobal('fetch', fetchSimulado)
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('serviços de análises', () => {
  it('lista o histórico apenas com os filtros informados', async () => {
    fetchSimulado.mockResolvedValue(respostaJson([]))

    await listAnalises('arm-1', {
      escopo: 'completo',
      refilId: 'refil 1',
      limite: 5,
    })

    expect(fetchSimulado.mock.calls[0][0]).toBe(
      urlDaApi(
        'armadilhas/arm-1/analises?escopo=completo&refil_id=refil+1&limite=5',
      ),
    )
    expect(fetchSimulado.mock.calls[0][1].method).toBe('GET')
  })

  it('não inclui parâmetros ausentes no histórico', async () => {
    fetchSimulado.mockResolvedValue(respostaJson([]))

    await listAnalises('arm-1')

    expect(fetchSimulado.mock.calls[0][0]).toBe(
      urlDaApi('armadilhas/arm-1/analises'),
    )
  })

  it('envia imagem e armadilha em multipart sem definir Content-Type', async () => {
    const arquivo = new File(['imagem'], 'armadilha.png', { type: 'image/png' })
    const resposta = {
      id: 'analise-1',
      refil_id: 'refil-1',
      armadilha_id: 'arm-1',
      analisado_em: '2026-10-08T12:00:00Z',
      percentual_coberto: 64.3,
      status: 'atencao',
      modelo_versao: 'v1',
      imagem_url: '/api/analises/analise-1/imagem',
    }
    fetchSimulado.mockResolvedValue(respostaJson(resposta, 201))

    await expect(createAnalise('arm-1', arquivo)).resolves.toEqual(resposta)

    const [url, init] = fetchSimulado.mock.calls[0] as [string, RequestInit]
    expect(url).toBe(urlDaApi('analises'))
    expect(init.method).toBe('POST')
    expect(init.body).toBeInstanceOf(FormData)
    expect((init.body as FormData).get('armadilha_id')).toBe('arm-1')
    expect((init.body as FormData).get('imagem')).toBeInstanceOf(File)
    expect(init.headers).toEqual({ Accept: 'application/json' })
    expect(init.signal).toBeInstanceOf(AbortSignal)
  })

  it('reserva 40 segundos para transferir a imagem e concluir a inferência', async () => {
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

    const rejeicao = expect(
      createAnalise(
        'arm-1',
        new File(['imagem'], 'armadilha.png', { type: 'image/png' }),
      ),
    ).rejects.toMatchObject({ codigo: 'TEMPO_ESGOTADO', status: 0 })
    await vi.advanceTimersByTimeAsync(40_000)
    await rejeicao
  })

  it('consulta uma análise pelo identificador', async () => {
    fetchSimulado.mockResolvedValue(respostaJson({ id: 'analise-1' }))

    await expect(getAnalise('analise-1')).resolves.toEqual({ id: 'analise-1' })
    expect(fetchSimulado.mock.calls[0][0]).toBe(
      urlDaApi('analises/analise-1'),
    )
  })
})
