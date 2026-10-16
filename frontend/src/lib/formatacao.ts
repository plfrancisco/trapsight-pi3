import type { StatusAnalise } from '../services/tipos'

const ROTULOS_STATUS: Record<StatusAnalise, string> = {
  ok: 'OK',
  atencao: 'Atenção',
  trocar: 'Trocar',
}

/** Apresenta um percentual com duas casas e vírgula decimal. */
export function formatPercentual(valor: number | null): string {
  if (valor === null) return '—'
  return new Intl.NumberFormat('pt-BR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(valor) + '%'
}

/** Formata uma data civil sem convertê-la pelo fuso horário local. */
export function formatData(data: string): string {
  const partes = /^(\d{4})-(\d{2})-(\d{2})$/.exec(data)
  if (!partes) return data
  return partes[3] + '/' + partes[2] + '/' + partes[1]
}

/** Formata um instante usando o locale brasileiro e o fuso horário local. */
export function formatDataHora(instanteIso: string): string {
  return new Date(instanteIso).toLocaleString('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'short',
  })
}

/** Traduz a estimativa de dias para saturação em um rótulo conciso. */
export function formatDiasAteSaturar(dias: number | null): string {
  if (dias === null) return 'Sem estimativa'
  if (dias <= 0) return 'Trocar agora'
  return dias === 1 ? '1 dia' : dias + ' dias'
}

/** Traduz o valor técnico do status para o texto mostrado na interface. */
export function rotuloStatus(status: StatusAnalise): string {
  return ROTULOS_STATUS[status]
}
