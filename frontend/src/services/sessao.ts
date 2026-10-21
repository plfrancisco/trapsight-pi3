/*
 * Estado de sessão mantido APENAS em memória.
 *
 * O token CSRF nunca é gravado em localStorage nem em sessionStorage: qualquer
 * script da origem os lê, e a sessão em si vive num cookie HttpOnly que o
 * JavaScript não enxerga. Ao recarregar a página, o token é recuperado por
 * `GET /api/auth/me`.
 */

let tokenCsrf: string | null = null

type Ouvinte = () => void
const ouvintesDeExpiracao = new Set<Ouvinte>()

/** Guarda o token CSRF recebido no login, no `me` ou na troca de senha. */
export function definirCsrf(token: string): void {
  tokenCsrf = token
}

/** Devolve o token CSRF atual, ou null sem sessão. */
export function obterCsrf(): string | null {
  return tokenCsrf
}

/** Esquece o token CSRF (logout, expiração). */
export function limparCsrf(): void {
  tokenCsrf = null
}

/**
 * Registra um ouvinte chamado quando a API responde que a sessão não existe mais.
 *
 * @param ouvinte Função chamada a cada resposta `NAO_AUTENTICADO`.
 * @returns Função que cancela o registro.
 */
export function assinarSessaoExpirada(ouvinte: Ouvinte): () => void {
  ouvintesDeExpiracao.add(ouvinte)
  return () => {
    ouvintesDeExpiracao.delete(ouvinte)
  }
}

/** Avisa os ouvintes de que a sessão deixou de valer no servidor. */
export function notificarSessaoExpirada(): void {
  for (const ouvinte of [...ouvintesDeExpiracao]) ouvinte()
}
