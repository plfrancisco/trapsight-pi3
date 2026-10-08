const apiUrl = import.meta.env.VITE_API_URL?.trim()

if (!apiUrl) {
  throw new Error('A variável pública VITE_API_URL é obrigatória.')
}

/** Endereço público usado pelo frontend para localizar a API. */
export const API_URL = apiUrl
