import { useCallback, useEffect, useState } from 'react'

export type Tema = 'claro' | 'escuro'

const CHAVE_TEMA = 'trapsight:tema'

/** Lê a preferência visual sem impedir a interface quando o armazenamento falha.
 * @returns O tema salvo ou o tema claro usado como padrão.
 */
function lerPreferenciaDeTema(): Tema {
  if (typeof window === 'undefined') return 'claro'

  try {
    return window.localStorage.getItem(CHAVE_TEMA) === 'escuro'
      ? 'escuro'
      : 'claro'
  } catch {
    return 'claro'
  }
}

/** Mantém o tema visual do aplicativo sincronizado com a raiz do documento.
 * @returns O tema atual e uma ação para alterná-lo.
 */
export function useTema() {
  const [tema, setTema] = useState<Tema>(lerPreferenciaDeTema)

  useEffect(() => {
    document.documentElement.dataset.theme = tema
    document.documentElement.style.colorScheme =
      tema === 'escuro' ? 'dark' : 'light'
    const corDaBarra = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')
    if (corDaBarra) corDaBarra.content = tema === 'escuro' ? '#101611' : '#f8faf8'

    try {
      window.localStorage.setItem(CHAVE_TEMA, tema)
    } catch {
      // A preferência continua funcionando na sessão atual sem armazenamento.
    }
  }, [tema])

  const alternarTema = useCallback(() => {
    setTema((atual) => (atual === 'claro' ? 'escuro' : 'claro'))
  }, [])

  return { tema, alternarTema }
}
