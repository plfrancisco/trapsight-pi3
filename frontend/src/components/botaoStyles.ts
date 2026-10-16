export type BotaoVariante = 'primario' | 'secundario' | 'discreto'
export type BotaoTamanho = 'compacto' | 'padrao' | 'amplo'

export const CLASSES_POR_VARIANTE: Record<BotaoVariante, string> = {
  primario:
    'bg-emerald-900 text-white transition-colors hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-60',
  secundario:
    'border border-slate-300 bg-white text-slate-800 transition-colors hover:bg-slate-100',
  discreto: 'text-slate-700 hover:bg-slate-100',
}

export const CLASSES_TAMANHO: Record<BotaoTamanho, string> = {
  compacto: 'px-3 py-2',
  padrao: 'px-4 py-2.5',
  amplo: 'px-5 py-2.5',
}

export const CLASSES_BASE =
  'inline-flex min-h-11 items-center justify-center rounded-lg text-sm font-semibold focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-800'

/** Combina as classes base, de tamanho e de variante com as extras do chamador.
 * @param variante Aparência visual da ação.
 * @param tamanho Espaçamento interno da ação.
 * @param extras Classes adicionais, aplicadas por último.
 * @returns Lista de classes separadas por espaço.
 */
export function classesBotao(
  variante: BotaoVariante,
  tamanho: BotaoTamanho,
  extras?: string,
): string {
  return [
    CLASSES_BASE,
    CLASSES_TAMANHO[tamanho],
    CLASSES_POR_VARIANTE[variante],
    extras,
  ]
    .filter(Boolean)
    .join(' ')
}
