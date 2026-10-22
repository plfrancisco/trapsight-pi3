import imagemStickflyK45 from '../assets/modelos/stickfly-k45.webp'

const IMAGENS_POR_MODELO: Record<string, string> = {
  stickflyk45: imagemStickflyK45,
}

/** Resolve a imagem de catálogo pelo código ou nome conhecido do modelo.
 * @param referencia Código ou nome retornado pela API.
 * @returns Caminho empacotado pelo Vite ou `null` quando não há imagem cadastrada.
 */
export function imagemDoModelo(
  referencia: string | null | undefined,
): string | null {
  const chave = referencia?.toLocaleLowerCase('pt-BR').replace(/[^a-z0-9]/g, '')
  return chave ? IMAGENS_POR_MODELO[chave] ?? null : null
}
