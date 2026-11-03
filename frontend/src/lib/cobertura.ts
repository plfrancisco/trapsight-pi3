import type { Analise } from '../services/tipos'
import { LIMIAR_TROCAR } from './limiares'
import { formatIndiceSaturacao, indiceSaturacao } from './saturacao'

/** Ponto numérico do eixo temporal do gráfico; `percentual` guarda o índice de saturação. */
export interface PontoCobertura {
  instante: number
  percentual: number
}

/** Converte medições cronológicas em coordenadas do gráfico de saturação.
 * @param analises Medições retornadas em ordem cronológica crescente.
 * @param limiarTrocar Limiar de troca em cobertura real.
 * @returns Pontos com o instante e o índice de saturação de cada medição.
 */
export function buildSerieCobertura(
  analises: readonly Pick<Analise, 'analisado_em' | 'percentual_coberto'>[],
  limiarTrocar: number = LIMIAR_TROCAR,
): PontoCobertura[] {
  return analises.map((analise) => ({
    instante: Date.parse(analise.analisado_em),
    percentual: indiceSaturacao(analise.percentual_coberto, limiarTrocar),
  }))
}

/** Resume a primeira e a última medição para a descrição acessível do gráfico.
 * @param analises Medições retornadas em ordem cronológica crescente.
 * @param limiarTrocar Limiar de troca em cobertura real.
 * @returns Uma descrição em português brasileiro com contagem e extremos.
 */
export function buildResumoCobertura(
  analises: readonly Pick<Analise, 'percentual_coberto'>[],
  limiarTrocar: number = LIMIAR_TROCAR,
): string {
  if (analises.length === 0) return 'Evolução da saturação: 0 medições'

  const primeira = formatIndiceSaturacao(analises[0].percentual_coberto, limiarTrocar)
  const ultima = formatIndiceSaturacao(
    analises[analises.length - 1].percentual_coberto,
    limiarTrocar,
  )
  const rotuloMedicao = analises.length === 1 ? 'medição' : 'medições'

  return `Evolução da saturação: ${analises.length} ${rotuloMedicao}, de ${primeira} a ${ultima}`
}
