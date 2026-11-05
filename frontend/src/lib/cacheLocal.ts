/*
 * Cache local dos dados do usuário, para o aplicativo abrir já preenchido.
 *
 * Fica no localStorage e NUNCA no Cache Storage do service worker, que continua
 * guardando só o casco público. Guarda apenas o necessário para desenhar a tela
 * (nome e papel do usuário, última lista de armadilhas): nada de token, CSRF,
 * e-mail ou fotos. Tudo expira em 24 h e é apagado no logout, em qualquer 401, na
 * troca de conta e na inatividade.
 */

/** Versão do formato; mudar este valor descarta o que foi gravado por versões antigas. */
const VERSAO = 'v1'
const PREFIXO = `trapsight:cache:${VERSAO}:`
const PREFIXO_GERAL = 'trapsight:cache:'
/** Último instante de atividade do usuário, compartilhado entre as abas. */
export const CHAVE_ATIVIDADE = 'trapsight:ultima-atividade'

/** Quanto tempo um dado guardado continua valendo. */
export const VALIDADE_CACHE_MS = 24 * 60 * 60 * 1000

export const CHAVE_SESSAO = 'sessao'
export const CHAVE_ARMADILHAS = 'armadilhas'

interface Registro<T> {
  salvoEm: number
  valor: T
}

function armazenamento(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage
  } catch {
    return null
  }
}

/** Lê um dado guardado, ou `null` se não existir, tiver vencido ou estiver malformado.
 * @param chave Nome do dado (sem prefixo).
 * @param validar Confere o formato do valor; um valor que não passa é descartado.
 */
export function lerCache<T>(chave: string, validar?: (valor: unknown) => valor is T): T | null {
  const deposito = armazenamento()
  if (!deposito) return null

  try {
    const bruto = deposito.getItem(PREFIXO + chave)
    if (bruto === null) return null

    const registro = JSON.parse(bruto) as Partial<Registro<unknown>> | null
    const valido =
      registro !== null
      && typeof registro === 'object'
      && typeof registro.salvoEm === 'number'
      && Date.now() - registro.salvoEm < VALIDADE_CACHE_MS
      && Date.now() >= registro.salvoEm
      && 'valor' in registro
      && (validar === undefined || validar(registro.valor))
    if (!valido) {
      deposito.removeItem(PREFIXO + chave)
      return null
    }
    return registro.valor as T
  } catch {
    return null
  }
}

/** Guarda um dado com a data atual; falhas de armazenamento são ignoradas. */
export function gravarCache<T>(chave: string, valor: T): void {
  const deposito = armazenamento()
  if (!deposito) return

  try {
    const registro: Registro<T> = { salvoEm: Date.now(), valor }
    deposito.setItem(PREFIXO + chave, JSON.stringify(registro))
  } catch {
    // Sem espaço ou com o armazenamento bloqueado, o aplicativo só abre sem o cache.
  }
}

/** Apaga tudo o que o aplicativo guardou sobre o usuário neste aparelho.
 * Preferências sem dado pessoal (tema, convite de instalação) ficam.
 */
export function limparCacheUsuario(): void {
  const deposito = armazenamento()
  if (!deposito) return

  try {
    const chaves: string[] = []
    for (let indice = 0; indice < deposito.length; indice += 1) {
      const chave = deposito.key(indice)
      if (chave !== null && (chave.startsWith(PREFIXO_GERAL) || chave === CHAVE_ATIVIDADE)) {
        chaves.push(chave)
      }
    }
    chaves.forEach((chave) => deposito.removeItem(chave))
  } catch {
    // Se o armazenamento recusar a limpeza, nada mais pode ser feito aqui.
  }
}
