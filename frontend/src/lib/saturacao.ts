import { formatPercentual } from './formatacao'
import { LIMIAR_TROCAR } from './limiares'

/** Índice mostrado quando a cobertura real chega ao limiar de troca. */
const INDICE_NO_LIMIAR_DE_TROCA = 80

/** Converte a cobertura real da placa no índice de saturação do refil.
 *
 * É só apresentação: a API, o banco e os limiares seguem com a cobertura real.
 * O índice faz o limiar de troca valer 80, em vez de um "20%" que parece pouco.
 * @param percentualCoberto Cobertura real medida pelo modelo, de 0 a 100.
 * @param limiarTrocar Limiar de troca em cobertura real; zero ou negativo usa o padrão.
 * @returns Índice de 0 a 100, com 100 como teto.
 */
export function indiceSaturacao(
  percentualCoberto: number,
  limiarTrocar: number = LIMIAR_TROCAR,
): number {
  const limiar = limiarTrocar > 0 ? limiarTrocar : LIMIAR_TROCAR
  const indice = (percentualCoberto / limiar) * INDICE_NO_LIMIAR_DE_TROCA
  return Math.min(100, Math.max(0, indice))
}

/** Formata o índice de saturação com duas casas e vírgula decimal.
 * @param percentualCoberto Cobertura real, ou null quando não há medição.
 * @param limiarTrocar Limiar de troca em cobertura real.
 * @returns Texto como "80,00%", ou "—" sem medição.
 */
export function formatIndiceSaturacao(
  percentualCoberto: number | null,
  limiarTrocar: number = LIMIAR_TROCAR,
): string {
  if (percentualCoberto === null) return '—'
  return formatPercentual(indiceSaturacao(percentualCoberto, limiarTrocar))
}
