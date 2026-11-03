import { useEffect, useState } from 'react'

/** Intervalo entre as atualizações do progresso, também a cadência de leitura da barra. */
export const INTERVALO_PROGRESSO_MS = 250
/** Constante de tempo da curva: com ~4 s a barra passa dos 60%, ritmo de uma análise típica. */
const TAU_MS = 4000
/** Valor para o qual a barra tende enquanto a resposta não chega. */
const ASSINTOTA = 90
/** A barra nunca passa disto sem a resposta; só a conclusão leva a 100%. */
const TETO_ANDAMENTO = 95
/** Abaixo disto a fase é de envio da foto; acima, o modelo está medindo. */
const LIMITE_ENVIO = 15

export type FaseProgresso = 'enviando' | 'medindo' | 'concluida'

/** Calcula o progresso estimado depois de certo tempo de espera.
 *
 * A API faz uma única chamada de uns 5 s e não informa o andamento real, então o
 * valor é uma ESTIMATIVA: sobe de forma suave rumo a 90% e nunca passa de 95% sem
 * a resposta. Só a conclusão leva a barra a 100%.
 * @param decorridoMs Tempo desde o início do envio, em milissegundos.
 * @returns Percentual entre 0 e 95.
 */
export function percentualEstimado(decorridoMs: number): number {
  const decorrido = Math.max(0, decorridoMs)
  return Math.min(TETO_ANDAMENTO, ASSINTOTA * (1 - Math.exp(-decorrido / TAU_MS)))
}

/** Traduz o percentual na fase mostrada ao usuário. */
export function faseDoProgresso(percentual: number): FaseProgresso {
  if (percentual >= 100) return 'concluida'
  return percentual < LIMITE_ENVIO ? 'enviando' : 'medindo'
}

/** Acompanha o progresso estimado de uma análise desde que o componente monta.
 * @param concluido Verdadeiro quando a resposta chegou; leva o progresso a 100%.
 * @returns O percentual atual (0 a 100, só sobe) e a fase correspondente.
 */
export function useProgressoEstimado(concluido: boolean): {
  percentual: number
  fase: FaseProgresso
} {
  const [inicio] = useState(() => Date.now())
  const [estimado, setEstimado] = useState(0)

  useEffect(() => {
    if (concluido) return undefined
    const intervalo = setInterval(() => {
      setEstimado((atual) => Math.max(atual, percentualEstimado(Date.now() - inicio)))
    }, INTERVALO_PROGRESSO_MS)
    return () => clearInterval(intervalo)
  }, [concluido, inicio])

  const percentual = concluido ? 100 : estimado
  return { percentual, fase: faseDoProgresso(percentual) }
}
