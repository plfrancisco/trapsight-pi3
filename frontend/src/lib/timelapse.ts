import type { RefilAnterior } from '../services/tipos'

export const VELOCIDADE_PADRAO_MS = 500
export const VELOCIDADE_MIN_MS = 200
export const VELOCIDADE_MAX_MS = 2000

/** Mantém a velocidade do quadro dentro da faixa suportada pelo controle.
 * @param velocidadeMs Velocidade solicitada em milissegundos por quadro.
 * @returns Velocidade limitada ou o padrão quando o valor não é finito.
 */
export function limitarVelocidade(velocidadeMs: number): number {
  if (!Number.isFinite(velocidadeMs)) return VELOCIDADE_PADRAO_MS
  return Math.min(VELOCIDADE_MAX_MS, Math.max(VELOCIDADE_MIN_MS, velocidadeMs))
}

/** Obtém o próximo índice quando ainda há um quadro adiante.
 * @param indiceAtual Índice do quadro em exibição.
 * @param quantidadeQuadros Número de quadros disponíveis.
 * @returns Próximo índice ou null quando a sequência deve parar.
 */
export function proximoIndice(
  indiceAtual: number,
  quantidadeQuadros: number,
): number | null {
  if (!Number.isInteger(indiceAtual) || !Number.isInteger(quantidadeQuadros)) {
    return null
  }
  if (quantidadeQuadros < 1 || indiceAtual < 0 || indiceAtual >= quantidadeQuadros - 1) {
    return null
  }
  return indiceAtual + 1
}

/** Localiza a análise com instante mais próximo, mantendo a primeira em caso de empate.
 * @param instantes Instantes ordenados dos quadros, em milissegundos.
 * @param instante Instante escolhido no gráfico, em milissegundos.
 * @returns Índice mais próximo ou -1 quando não há instante válido.
 */
export function indiceQuadroMaisProximo(
  instantes: readonly number[],
  instante: number,
): number {
  if (instantes.length === 0) return -1
  if (!Number.isFinite(instante)) return 0

  let indiceMaisProximo = -1
  let distanciaMaisCurta = Number.POSITIVE_INFINITY

  instantes.forEach((instanteQuadro, indice) => {
    if (!Number.isFinite(instanteQuadro)) return
    const distancia = Math.abs(instanteQuadro - instante)
    if (distancia < distanciaMaisCurta) {
      indiceMaisProximo = indice
      distanciaMaisCurta = distancia
    }
  })

  return indiceMaisProximo === -1 ? 0 : indiceMaisProximo
}

/** Converte a posição temporal de um arrasto para o quadro mais próximo.
 * @param instantes Instantes dos quadros em milissegundos.
 * @param instanteArrastado Instante apontado no gráfico.
 * @returns Índice do quadro mais próximo ou -1 quando a lista está vazia.
 */
export function mapearArrastoParaIndice(
  instantes: readonly number[],
  instanteArrastado: number,
): number {
  return indiceQuadroMaisProximo(instantes, instanteArrastado)
}

/** Retorna o instante associado a um índice válido de quadro.
 * @param instantes Instantes dos quadros em milissegundos.
 * @param indice Índice solicitado.
 * @returns Instante do quadro ou null quando o índice não existe.
 */
export function instanteDoQuadro(
  instantes: readonly number[],
  indice: number,
): number | null {
  if (!Number.isInteger(indice) || indice < 0 || indice >= instantes.length) {
    return null
  }
  const instante = instantes[indice]
  return Number.isFinite(instante) ? instante : null
}

/** Converte as datas civis de troca para instantes locais do marcador do gráfico.
 * @param refis Refis anteriores registrados pela API.
 * @returns Instantes válidos de troca, em milissegundos.
 */
export function instantesTroca(
  refis: readonly Pick<RefilAnterior, 'data_troca'>[],
): number[] {
  return refis.flatMap(({ data_troca }) => {
    const partes = /^(\d{4})-(\d{2})-(\d{2})$/.exec(data_troca)
    if (!partes) return []

    const ano = Number(partes[1])
    const mes = Number(partes[2])
    const dia = Number(partes[3])
    const data = new Date(ano, mes - 1, dia)
    if (
      data.getFullYear() !== ano ||
      data.getMonth() !== mes - 1 ||
      data.getDate() !== dia
    ) {
      return []
    }

    // A data de troca não tem horário; meia-noite local preserva o dia mostrado no eixo.
    return [data.getTime()]
  })
}
