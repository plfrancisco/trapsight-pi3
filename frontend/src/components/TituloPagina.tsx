import { useEffect } from 'react'
import { matchPath, useLocation } from 'react-router'

const titulos: [string, string][] = [
  ['/', 'Dashboard'],
  ['/login', 'Entrar'],
  ['/armadilhas/nova', 'Nova armadilha'],
  ['/armadilhas/:id/editar', 'Editar armadilha'],
  ['/armadilhas/:id', 'Detalhe da armadilha'],
  ['/analises/nova', 'Nova análise'],
  ['/contas', 'Contas'],
  ['/configuracoes', 'Configurações'],
  ['/conta/senha', 'Alterar senha'],
]

/** Identifica a tela atual na aba do navegador e no histórico de navegação. */
export default function TituloPagina() {
  const { pathname } = useLocation()
  useEffect(() => {
    const titulo = titulos.find(([rota]) => matchPath(rota, pathname))?.[1]
      ?? 'Página não encontrada'
    document.title = `${titulo} | TrapSight`
  }, [pathname])
  return null
}
