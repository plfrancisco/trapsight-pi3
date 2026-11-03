import { expect, it } from 'vitest'
import { configurarFavicon } from './favicon'
import faviconUrl from '../assets/favicon.svg'

it('define um único favicon SVG mesmo quando inicializado novamente', () => {
  configurarFavicon()
  configurarFavicon()
  const icones = document.querySelectorAll<HTMLLinkElement>('link[rel="icon"]')
  expect(icones).toHaveLength(1)
  expect(icones[0].type).toBe('image/svg+xml')
  expect(icones[0].href).toBe(new URL(faviconUrl, document.baseURI).href)
  icones[0].remove()
})
