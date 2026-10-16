const MILISSEGUNDOS_POR_DIA = 24 * 60 * 60 * 1000

/** Calcula dias completos desde o início do alerta usando um instante informado.
 * @param dataInicio Instante ISO em que a armadilha entrou em estado de alerta.
 * @param instanteReferencia Instante usado como fim do intervalo.
 * @returns Número inteiro de dias completos, sem valores negativos.
 */
export function calculateDiasEmAlerta(
  dataInicio: string,
  instanteReferencia: Date,
): number {
  const inicioEmMilissegundos = Date.parse(dataInicio)
  const diasDecorridos = Math.floor(
    (instanteReferencia.getTime() - inicioEmMilissegundos) /
      MILISSEGUNDOS_POR_DIA,
  )
  return Math.max(0, diasDecorridos)
}
