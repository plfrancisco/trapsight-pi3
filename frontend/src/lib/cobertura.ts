import type { Analise } from '../services/tipos'
import { formatPercentual } from './formatacao'

/** Ponto numérico usado pelo eixo temporal do gráfico de cobertura. */
export interface PontoCobertura {
  instante: number
  percentual: number
}

/** Converte medições cronológicas para coordenadas sem alterar seus valores.
 * @param analises Medições retornadas em ordem cronológica crescente.
 * @returns Pontos numéricos prontos para o eixo temporal do gráfico.
 */
export function buildSerieCobertura(
  analises: readonly Pick<Analise, 'analisado_em' | 'percentual_coberto'>[],
): PontoCobertura[] {
  return analises.map((analise) => ({
    instante: Date.parse(analise.analisado_em),
    percentual: analise.percentual_coberto,
  }))
}

/** Resume a primeira e a última medição para a descrição acessível do gráfico.
 * @param analises Medições retornadas em ordem cronológica crescente.
 * @returns Uma descrição em português brasileiro com contagem e extremos.
 */
export function buildResumoCobertura(
  analises: readonly Pick<Analise, 'percentual_coberto'>[],
): string {
  if (analises.length === 0) return 'Evolução da cobertura: 0 medições'

  const primeira = formatPercentual(analises[0].percentual_coberto)
  const ultima = formatPercentual(analises[analises.length - 1].percentual_coberto)
  const rotuloMedicao = analises.length === 1 ? 'medição' : 'medições'

  return `Evolução da cobertura: ${analises.length} ${rotuloMedicao}, de ${primeira} a ${ultima}`
}
