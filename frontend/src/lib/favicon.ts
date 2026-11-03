import faviconUrl from '../assets/favicon.svg'

/** Define o ícone empacotado pelo Vite, inclusive em instalações sob um subcaminho. */
export function configurarFavicon() {
  const icone = document.querySelector<HTMLLinkElement>('link[rel="icon"]')
    ?? document.createElement('link')
  icone.rel = 'icon'
  icone.type = 'image/svg+xml'
  icone.href = faviconUrl
  document.head.append(icone)
}
