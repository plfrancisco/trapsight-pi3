import { API_BASE } from '../config'

/** Converte um caminho relativo da API em URL absoluta da mesma origem. */
export function urlAbsoluta(caminhoRelativo: string): string {
  const origem = API_BASE.origin
  const url = new URL(caminhoRelativo, origem)
  if (url.origin !== origem) {
    throw new TypeError('A URL de mídia precisa permanecer na origem da API.')
  }
  return url.toString()
}

function urlRecursoAnalise(analiseId: string, recurso: 'imagem' | 'mascara'): string {
  const prefixo = API_BASE.pathname.replace(/\/+$/, '')
  const caminho =
    prefixo + '/analises/' + encodeURIComponent(analiseId) + '/' + recurso
  return urlAbsoluta(caminho)
}

/** Retorna a URL absoluta da imagem original de uma análise sem fazer requisição. */
export function urlImagemAnalise(analiseId: string): string {
  return urlRecursoAnalise(analiseId, 'imagem')
}

/** Retorna a URL absoluta da máscara de uma análise sem fazer requisição. */
export function urlMascaraAnalise(analiseId: string): string {
  return urlRecursoAnalise(analiseId, 'mascara')
}
