import { API_URL } from '../config'
import { ApiError } from './erros'

const TIMEOUT_PADRAO_MS = 15_000
export const TIMEOUT_UPLOAD_MS = 40_000

interface OpcoesRequisicao {
  method?: string
  body?: unknown
  signal?: AbortSignal
  timeoutMs?: number
}

function criarErroDeRespostaInvalida(status: number): ApiError {
  return new ApiError(
    'RESPOSTA_INVALIDA',
    'A API retornou uma resposta fora do formato esperado.',
    status,
  )
}

function interpretarEnvelopeDeErro(texto: string, status: number): ApiError {
  let resposta: unknown

  try {
    resposta = JSON.parse(texto)
  } catch {
    return criarErroDeRespostaInvalida(status)
  }

  if (!resposta || typeof resposta !== 'object' || Array.isArray(resposta)) {
    return criarErroDeRespostaInvalida(status)
  }

  const envelope = (resposta as { erro?: unknown }).erro
  if (!envelope || typeof envelope !== 'object' || Array.isArray(envelope)) {
    return criarErroDeRespostaInvalida(status)
  }

  const erro = envelope as {
    codigo?: unknown
    mensagem?: unknown
    detalhes?: unknown
  }
  const detalhesValidos =
    erro.detalhes === undefined ||
    (typeof erro.detalhes === 'object' &&
      erro.detalhes !== null &&
      !Array.isArray(erro.detalhes))

  if (
    typeof erro.codigo !== 'string' ||
    typeof erro.mensagem !== 'string' ||
    !detalhesValidos
  ) {
    return criarErroDeRespostaInvalida(status)
  }

  return new ApiError(
    erro.codigo,
    erro.mensagem,
    status,
    erro.detalhes as Record<string, unknown> | undefined,
  )
}

function montarUrl(caminho: string): string {
  const base = API_URL.replace(/\/+$/, '') + '/'
  return new URL(caminho.replace(/^\/+/, ''), base).toString()
}

/**
 * Envia uma requisição à API e converte falhas de transporte e envelopes HTTP
 * para ApiError.
 *
 * @param caminho Caminho relativo à base pública da API.
 * @param opcoes Método, corpo, cancelamento e timeout da requisição.
 * @returns O corpo JSON validado pelo chamador.
 * @throws ApiError quando a API falha, retorna JSON inválido ou excede o timeout.
 */
export async function request<T>(
  caminho: string,
  opcoes: OpcoesRequisicao = {},
): Promise<T> {
  const controlador = new AbortController()
  const sinalExterno = opcoes.signal
  let expirou = false

  if (sinalExterno?.aborted) {
    throw (
      sinalExterno.reason ?? new DOMException('Requisição cancelada.', 'AbortError')
    )
  }

  const cancelarComSinalExterno = () => controlador.abort(sinalExterno?.reason)
  sinalExterno?.addEventListener('abort', cancelarComSinalExterno, { once: true })

  const timeout = setTimeout(() => {
    expirou = true
    controlador.abort()
  }, opcoes.timeoutMs ?? TIMEOUT_PADRAO_MS)

  const cabecalhos: Record<string, string> = { Accept: 'application/json' }

  let corpo: BodyInit | undefined
  if (opcoes.body !== undefined) {
    if (typeof FormData !== 'undefined' && opcoes.body instanceof FormData) {
      corpo = opcoes.body
    } else {
      corpo = JSON.stringify(opcoes.body)
      cabecalhos['Content-Type'] = 'application/json'
    }
  }

  try {
    const resposta = await fetch(montarUrl(caminho), {
      method: opcoes.method ?? 'GET',
      headers: cabecalhos,
      body: corpo,
      signal: controlador.signal,
    })
    const texto = await resposta.text()

    if (!resposta.ok) {
      throw interpretarEnvelopeDeErro(texto, resposta.status)
    }

    try {
      return JSON.parse(texto) as T
    } catch {
      throw criarErroDeRespostaInvalida(resposta.status)
    }
  } catch (erro) {
    if (erro instanceof ApiError) {
      throw erro
    }
    if (expirou) {
      throw new ApiError(
        'TEMPO_ESGOTADO',
        'A requisição excedeu o tempo limite.',
        0,
      )
    }
    if (sinalExterno?.aborted) {
      throw erro
    }
    throw new ApiError(
      'FALHA_DE_REDE',
      'Não foi possível conectar à API.',
      0,
    )
  } finally {
    clearTimeout(timeout)
    sinalExterno?.removeEventListener('abort', cancelarComSinalExterno)
  }
}
