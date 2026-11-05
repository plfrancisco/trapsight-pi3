import { setCacheNameDetails } from 'workbox-core'
import {
  cleanupOutdatedCaches,
  matchPrecache,
  precacheAndRoute,
} from 'workbox-precaching'
import { NavigationRoute, registerRoute } from 'workbox-routing'
import { NetworkOnly } from 'workbox-strategies'
import type { PrecacheEntry } from 'workbox-precaching'

const manifestoInjetado = (self as typeof self & {
  __WB_MANIFEST: Array<string | PrecacheEntry>
}).__WB_MANIFEST
const caminhoApi = /^\/api(?:\/|$)/
const arquivoPertenceAoCasco = (entrada: string | PrecacheEntry): boolean => {
  const url = typeof entrada === 'string' ? entrada : entrada.url
  return (
    url === 'index.html' ||
    url.startsWith('assets/') ||
    /^icons\/[^/]+\.png$/i.test(url)
  )
}
const manifestoDoCasco = manifestoInjetado.filter(arquivoPertenceAoCasco)

setCacheNameDetails({ prefix: 'trapsight' })
cleanupOutdatedCaches()

registerRoute(
  ({ request, url }) =>
    request.method !== 'GET' ||
    url.origin !== self.location.origin ||
    caminhoApi.test(url.pathname),
  new NetworkOnly(),
)

registerRoute(
  new NavigationRoute(
    async ({ request }) => {
      try {
        return await fetch(request)
      } catch {
        return (await matchPrecache('/index.html')) ?? Response.error()
      }
    },
    { denylist: [/^\/api\//] },
  ),
)

precacheAndRoute(manifestoDoCasco)
