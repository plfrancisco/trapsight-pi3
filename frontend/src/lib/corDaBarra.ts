export type TemaDaBarra = 'claro' | 'escuro'

/** Sincroniza todas as meta tags theme-color com o fundo do tema ativo.
 * @param tema Tema visual ativo na aplicação.
 */
export function atualizarCorDaBarra(tema: TemaDaBarra): void {
  const cor = tema === 'escuro' ? '#0a1316' : '#f5f7f6'
  document.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]').forEach((meta) => {
    meta.content = cor
  })
}
