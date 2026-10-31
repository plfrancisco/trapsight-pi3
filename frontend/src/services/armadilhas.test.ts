import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { API_URL } from '../config'
import {
  createArmadilha,
  deleteFotoArmadilha,
  getArmadilha,
  listArmadilhas,
  replaceRefil,
  sendFotoArmadilha,
  updateArmadilha,
} from './armadilhas'
import { listModelos } from './modelos'

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
  vi.unstubAllGlobals()
})

describe('serviços de armadilhas', () => {
  it('lista armadilhas sem converter os campos da API', async () => {
    const dados = [
      {
        id: 'arm-1',
        identificador: 'ARM-001',
        localizacao: null,
        modelo: 'K-45',
        refil_ativo: null,
        percentual_atual: null,
        status: null,
        dias_ate_saturar: null,
        limiar_trocar: 20,
        foto_tipo: 'padrao',
        foto_url: null,
        ultima_analise_em: null,
        em_alerta_desde: null,
      },
    ]
    fetchSimulado.mockResolvedValue(respostaJson(dados))

    await expect(listArmadilhas()).resolves.toEqual(dados)

    expect(fetchSimulado).toHaveBeenCalledWith(
      urlDaApi('armadilhas'),
      expect.objectContaining({ method: 'GET' }),
    )
    expect(fetchSimulado.mock.calls[0][1].headers).toEqual({
      Accept: 'application/json',
    })
  })

  it('cria armadilha com JSON e mantém as chaves snake_case', async () => {
    const entrada = {
      identificador: 'ARM-002',
      data_instalacao: '2026-10-08',
      criar_refil_inicial: true,
    }
    const saida = {
      id: 'arm-2',
      identificador: 'ARM-002',
      modelo: null,
      localizacao: null,
      data_instalacao: '2026-10-08',
      refil_ativo: { id: 'ref-2', data_instalacao: '2026-10-08', dias_em_uso: 0 },
      refis_anteriores: [],
      percentual_atual: null,
      status: null,
      dias_ate_saturar: null,
      limiar_trocar: 20,
      foto_tipo: 'padrao',
      foto_url: null,
    }
    fetchSimulado.mockResolvedValue(respostaJson(saida, 201))

    await expect(createArmadilha(entrada)).resolves.toEqual(saida)

    const [url, init] = fetchSimulado.mock.calls[0] as [string, RequestInit]
    expect(url).toBe(urlDaApi('armadilhas'))
    expect(init.method).toBe('POST')
    expect(JSON.parse(String(init.body))).toEqual(entrada)
    expect(init.headers).toEqual({
      Accept: 'application/json',
      'Content-Type': 'application/json',
    })
  })

  it('consulta uma armadilha pelo identificador', async () => {
    fetchSimulado.mockResolvedValue(respostaJson({ id: 'a/b' }))

    await expect(getArmadilha('a/b')).resolves.toEqual({ id: 'a/b' })
    expect(fetchSimulado.mock.calls[0][0]).toBe(
      urlDaApi('armadilhas/a%2Fb'),
    )
  })

  it('atualiza somente os campos enviados por PATCH', async () => {
    const entrada = { localizacao: 'Área de recebimento' }
    fetchSimulado.mockResolvedValue(respostaJson({ id: 'arm-1', ...entrada }))

    await updateArmadilha('arm-1', entrada)

    const [url, init] = fetchSimulado.mock.calls[0] as [string, RequestInit]
    expect(url).toBe(urlDaApi('armadilhas/arm-1'))
    expect(init.method).toBe('PATCH')
    expect(JSON.parse(String(init.body))).toEqual(entrada)
  })

  it('registra uma troca de refil no endpoint da armadilha', async () => {
    const entrada = { data_instalacao: '2026-10-08' }
    const saida = {
      refil_encerrado: null,
      refil_novo: { id: 'ref-2', data_instalacao: '2026-10-08', dias_em_uso: 0 },
    }
    fetchSimulado.mockResolvedValue(respostaJson(saida, 201))

    await expect(replaceRefil('arm-1', entrada)).resolves.toEqual(saida)

    const [url, init] = fetchSimulado.mock.calls[0] as [string, RequestInit]
    expect(url).toBe(urlDaApi('armadilhas/arm-1/refis'))
    expect(init.method).toBe('POST')
    expect(JSON.parse(String(init.body))).toEqual(entrada)
  })
})

describe('serviço de modelos', () => {
  it('lista o catálogo sem converter os campos da API', async () => {
    const dados = [{ id: 'mod-1', codigo: 'stickfly-k45', nome: 'StickFly K-45' }]
    fetchSimulado.mockResolvedValue(respostaJson(dados))

    await expect(listModelos()).resolves.toEqual(dados)

    expect(fetchSimulado).toHaveBeenCalledWith(
      urlDaApi('modelos-armadilha'),
      expect.objectContaining({ method: 'GET' }),
    )
  })

  it('envia a foto como multipart no campo arquivo, sem Content-Type manual', async () => {
    fetchSimulado.mockResolvedValue(
      respostaJson({ foto_tipo: 'real', foto_url: '/api/armadilhas/arm-1/foto?v=1' }),
    )
    const arquivo = new File(['x'], 'foto.jpg', { type: 'image/jpeg' })

    await expect(sendFotoArmadilha('arm-1', arquivo)).resolves.toEqual({
      foto_tipo: 'real',
      foto_url: '/api/armadilhas/arm-1/foto?v=1',
    })

    expect(fetchSimulado).toHaveBeenCalledWith(
      urlDaApi('armadilhas/arm-1/foto'),
      expect.objectContaining({ method: 'PUT' }),
    )
    const opcoes = fetchSimulado.mock.calls[0][1]
    expect(opcoes.body).toBeInstanceOf(FormData)
    expect((opcoes.body as FormData).get('arquivo')).toBe(arquivo)
    expect(opcoes.headers['Content-Type']).toBeUndefined()
  })

  it('volta à foto padrão com DELETE e aceita a resposta 204', async () => {
    fetchSimulado.mockResolvedValue({ ok: true, status: 204, text: async () => '' } as Response)

    await expect(deleteFotoArmadilha('arm-1')).resolves.toBeUndefined()

    expect(fetchSimulado).toHaveBeenCalledWith(
      urlDaApi('armadilhas/arm-1/foto'),
      expect.objectContaining({ method: 'DELETE' }),
    )
  })
})
