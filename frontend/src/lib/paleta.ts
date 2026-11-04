/** Cores base dos status usadas nos gráficos e nas classes estáticas do badge.
 * As classes do StatusBadge permanecem literais para que o Tailwind as detecte.
 */
export const PALETA_STATUS = {
  ok: { linha: 'var(--app-status-ok)', texto: 'var(--app-status-ok-ink)' },
  atencao: { linha: 'var(--app-attention)', texto: 'var(--app-attention-ink)' },
  trocar: { linha: 'var(--app-danger)', texto: 'var(--app-danger-ink)' },
}
