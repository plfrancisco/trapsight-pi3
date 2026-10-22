export type BotaoVariante = 'primario' | 'secundario' | 'discreto'
export type BotaoTamanho = 'compacto' | 'padrao' | 'amplo'

export const CLASSES_POR_VARIANTE: Record<BotaoVariante, string> = {
  primario:
    'bg-app-primary text-app-on-primary transition-colors hover:bg-app-primary-hover disabled:cursor-not-allowed disabled:opacity-60',
  secundario:
    'border border-app-border bg-app-surface text-app-foreground transition-colors hover:bg-app-soft',
  discreto: 'text-app-muted transition-colors hover:bg-app-soft',
}

export const CLASSES_TAMANHO: Record<BotaoTamanho, string> = {
  compacto: 'px-3 py-2',
  padrao: 'px-4 py-2.5',
  amplo: 'px-5 py-2.5',
}

export const CLASSES_BASE =
  'button inline-flex min-h-11 cursor-pointer items-center justify-center rounded-[14px] text-sm font-semibold focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-primary'

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
