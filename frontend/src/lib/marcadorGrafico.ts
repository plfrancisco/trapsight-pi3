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
