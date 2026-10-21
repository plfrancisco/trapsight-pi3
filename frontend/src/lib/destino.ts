const DESTINO_PADRAO = '/'

/**
 * Valida o destino a visitar depois do login, impedindo *open redirect*: só
 * caminhos internos são aceitos, nunca um endereço de outro site.
 *
 * @param valor Valor recebido (por exemplo, do estado de navegação).
 * @param padrao Caminho usado quando o valor não é seguro.
 * @returns Um caminho interno que começa com uma única barra, ou o padrão.
 */
export function destinoSeguro(valor: unknown, padrao: string = DESTINO_PADRAO): string {
  if (typeof valor !== 'string') return padrao
  // "//dominio" e "/\dominio" são tratados como endereços de outro site pelos navegadores.
  if (!valor.startsWith('/') || valor.startsWith('//') || valor.includes('\\')) return padrao
  if ([...valor].some((caractere) => caractere.charCodeAt(0) < 32)) return padrao

  const caminho = valor.split(/[?#]/)[0]
  if (caminho === '/login') return padrao

  return valor
}

/**
 * Lê o destino guardado no estado de navegação e o valida.
 *
 * @param estado Estado de navegação do react-router (tipo desconhecido).
 * @returns Um caminho interno seguro ou o padrão.
 */
export function destinoDoEstado(estado: unknown): string {
  if (typeof estado !== 'object' || estado === null || !('destino' in estado)) {
    return DESTINO_PADRAO
  }
  return destinoSeguro(estado.destino)
}
