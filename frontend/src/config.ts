const apiUrl = import.meta.env.VITE_API_URL?.trim() || '/api'

/** Endereço público usado pelo frontend para localizar a API. */
export const API_URL = apiUrl

/**
 * Endereço base da API resolvido contra a origem da página. Aceita URL absoluta
 * (desenvolvimento) e caminho relativo como `/api` (produção, mesma origem).
 */
export const API_BASE = new URL(
  apiUrl.replace(/\/+$/, '') + '/',
  window.location.origin,
)

/**
 * Liga a exigência de login no frontend. É apenas apresentação (mostra a tela de
 * login e protege as rotas da interface): quem impõe a autenticação é sempre o
 * backend. Desligada, serve para testar a interface isolada.
 */
const autenticacaoConfigurada = import.meta.env.VITE_AUTENTICACAO_ATIVA
export const AUTENTICACAO_ATIVA =
  autenticacaoConfigurada === undefined
    ? import.meta.env.PROD
    : autenticacaoConfigurada === 'true'
