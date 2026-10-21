import { request } from './http'
import type { ModeloArmadilha } from './tipos'

/** Lista os modelos de armadilha pré-cadastrados pelo fabricante. */
export function listModelos(signal?: AbortSignal): Promise<ModeloArmadilha[]> {
  return request<ModeloArmadilha[]>('modelos-armadilha', { signal })
}
