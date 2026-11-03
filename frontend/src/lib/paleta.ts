/** Cores base dos status usadas nos gráficos e nas classes estáticas do badge.
 * As classes do StatusBadge permanecem literais para que o Tailwind as detecte.
 */
export const PALETA_STATUS = {
  ok: { linha: 'var(--app-primary)', texto: 'var(--app-primary-strong)' },
  atencao: { linha: 'var(--app-attention)', texto: 'var(--app-attention)' },
  trocar: { linha: 'var(--app-danger)', texto: 'var(--app-danger)' },
}
