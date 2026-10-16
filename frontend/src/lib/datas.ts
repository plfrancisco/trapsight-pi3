/** Formata o dia civil local sem converter o instante para UTC.
 * @param instante Instante do qual se obtém a data no fuso local.
 * @returns Data local no formato YYYY-MM-DD.
 */
export function localDateIso(instante: Date): string {
  const ano = instante.getFullYear()
  const mes = String(instante.getMonth() + 1).padStart(2, '0')
  const dia = String(instante.getDate()).padStart(2, '0')

  return `${ano}-${mes}-${dia}`
}
