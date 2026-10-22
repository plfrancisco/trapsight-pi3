/** Intervalo mensal usado para representar a previsão sem indicar um dia exato. */
export interface MesPrevistoTroca {
  inicio: number
  fim: number
  rotulo: string
}

/** Converte os dias restantes estimados pela API no mês previsto para a troca.
 * @param diasAteSaturar Dias estimados até alcançar o limite de troca.
 * @param referencia Data atual usada para calcular a previsão.
 * @returns O mês civil previsto ou null sem dados suficientes.
 */
export function calcularMesPrevistoTroca(
  diasAteSaturar: number | null,
  referencia = new Date(),
): MesPrevistoTroca | null {
  if (diasAteSaturar === null || !Number.isFinite(diasAteSaturar)) return null

  const dataPrevista = new Date(referencia)
  dataPrevista.setDate(dataPrevista.getDate() + Math.max(0, Math.floor(diasAteSaturar)))

  const inicio = new Date(dataPrevista.getFullYear(), dataPrevista.getMonth(), 1)
  const fim = new Date(dataPrevista.getFullYear(), dataPrevista.getMonth() + 1, 1)
  const mes = new Intl.DateTimeFormat('pt-BR', { month: 'long', year: 'numeric' })
    .format(dataPrevista)

  return {
    inicio: inicio.getTime(),
    fim: fim.getTime(),
    rotulo: mes.charAt(0).toLocaleUpperCase('pt-BR') + mes.slice(1),
  }
}
