import { request, TIMEOUT_UPLOAD_MS } from './http'
import type { Analise, FiltrosAnalises } from './tipos'

/** Lista análises aplicando apenas os filtros que foram informados. */
export function listAnalises(
  armadilhaId: string,
  filtros: FiltrosAnalises = {},
  signal?: AbortSignal,
): Promise<Analise[]> {
  const consulta = new URLSearchParams()
  if (filtros.escopo !== undefined) consulta.set('escopo', filtros.escopo)
  if (filtros.refilId !== undefined) consulta.set('refil_id', filtros.refilId)
  if (filtros.limite !== undefined) consulta.set('limite', String(filtros.limite))

  const textoConsulta = consulta.toString()
  const sufixo = textoConsulta ? '?' + textoConsulta : ''
  const caminho =
    'armadilhas/' + encodeURIComponent(armadilhaId) + '/analises' + sufixo
  return request<Analise[]>(caminho, { signal })
}

/** Envia imagem e identificador no formato multipart sem definir o boundary manualmente. */
export function createAnalise(
  armadilhaId: string,
  arquivo: File,
  signal?: AbortSignal,
): Promise<Analise> {
  const dados = new FormData()
  dados.append('imagem', arquivo)
  dados.append('armadilha_id', armadilhaId)
  return request<Analise>('analises', {
    method: 'POST',
    body: dados,
    signal,
    timeoutMs: TIMEOUT_UPLOAD_MS,
  })
}

/** Consulta o resultado persistido de uma análise. */
export function getAnalise(
  analiseId: string,
  signal?: AbortSignal,
): Promise<Analise> {
  return request<Analise>('analises/' + encodeURIComponent(analiseId), { signal })
}
