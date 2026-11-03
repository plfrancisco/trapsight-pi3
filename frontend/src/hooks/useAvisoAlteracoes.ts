import { useEffect, useRef, type RefObject } from 'react'

function assinatura(formulario: HTMLFormElement) {
  return JSON.stringify(Array.from(new FormData(formulario), ([nome, valor]) => [
    nome,
    typeof valor === 'string' ? valor : valor.name ? [valor.name, valor.size, valor.lastModified] : null,
  ]))
}

/** Avisa antes de fechar a página ou seguir um link com dados ainda não salvos. */
export function useAvisoAlteracoes(
  formulario: RefObject<HTMLFormElement | null>,
  pronto: boolean,
) {
  const salvo = useRef(false)

  useEffect(() => {
    const elemento = formulario.current
    if (!pronto || !elemento) return
    const inicial = assinatura(elemento)
    const temAlteracoes = () => !salvo.current && assinatura(elemento) !== inicial

    function antesDeFechar(evento: BeforeUnloadEvent) {
      if (!temAlteracoes()) return
      evento.preventDefault()
      evento.returnValue = ''
    }

    function antesDeNavegar(evento: MouseEvent) {
      if (evento.defaultPrevented || evento.button !== 0 || evento.ctrlKey
        || evento.metaKey || evento.shiftKey || evento.altKey) return
      const link = evento.target instanceof Element
        ? evento.target.closest<HTMLAnchorElement>('a[href]') : null
      if (!link || link.hasAttribute('download') || (link.target && link.target !== '_self')) return
      const destino = new URL(link.href)
      if (destino.pathname === location.pathname && destino.search === location.search) return
      if (temAlteracoes() && !window.confirm('Há alterações não salvas. Sair e descartá-las?')) {
        evento.preventDefault()
        evento.stopPropagation()
      }
    }

    window.addEventListener('beforeunload', antesDeFechar)
    document.addEventListener('click', antesDeNavegar, true)
    return () => {
      window.removeEventListener('beforeunload', antesDeFechar)
      document.removeEventListener('click', antesDeNavegar, true)
    }
  }, [formulario, pronto])

  return () => { salvo.current = true }
}
