import { CHAVE_ATIVIDADE } from './cacheLocal'

/** Sem nenhum toque, tecla ou rolagem por este tempo, a sessão é encerrada. */
export const LIMITE_INATIVIDADE_MS = 20 * 60 * 1000

/** Intervalo mínimo entre duas gravações do instante de atividade. */
export const INTERVALO_GRAVACAO_MS = 5_000

/** Registra que o usuário agiu agora.
 * @param agora Instante da atividade, em milissegundos.
 */
export function registrarAtividade(agora: number = Date.now()): void {
  try {
    window.localStorage.setItem(CHAVE_ATIVIDADE, String(agora))
  } catch {
    // Sem armazenamento, a contagem vale só enquanto a página estiver aberta.
  }
}

/** Lê o último instante de atividade registrado, ou `null` se não houver. */
export function lerUltimaAtividade(): number | null {
  try {
    const bruto = window.localStorage.getItem(CHAVE_ATIVIDADE)
    if (bruto === null) return null
    const valor = Number(bruto)
    return Number.isFinite(valor) && valor > 0 ? valor : null
  } catch {
    return null
  }
}

/** Diz se o tempo sem atividade já passou do limite.
 * @param ultima Último instante de atividade, ou `null` quando nunca houve.
 * @param agora Instante de referência.
 */
export function estaInativo(ultima: number | null, agora: number = Date.now()): boolean {
  return ultima !== null && agora - ultima >= LIMITE_INATIVIDADE_MS
}
