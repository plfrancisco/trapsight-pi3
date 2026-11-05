import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, it } from 'vitest'
import { pwaOptions } from '../../vite.config'

const raizFrontend = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const codigoWorker = readFileSync(resolve(raizFrontend, 'sw.ts'), 'utf8')
const codigoWorkerEmUmaLinha = codigoWorker.replace(/\s+/g, ' ')

it('mantém o precache no casco e força a rede para API, métodos e outras origens', async () => {
  expect(pwaOptions.strategies).toBe('injectManifest')
  expect(pwaOptions.injectManifest?.globPatterns).toEqual([
    'index.html',
    'assets/**/*',
    'icons/*.png',
  ])
  expect(pwaOptions.includeManifestIcons).toBe(false)
  expect(codigoWorker).toContain('manifestoInjetado.filter(arquivoPertenceAoCasco)')
  expect(codigoWorker).toContain("url === 'index.html'")
  expect(codigoWorker).toContain("url.startsWith('assets/')")
  expect(codigoWorker).toContain('/^icons\\/[^/]+\\.png$/i')
  expect(codigoWorker).toContain('new NetworkOnly()')
  expect(codigoWorker).toContain("request.method !== 'GET'")
  expect(codigoWorker).toContain('url.origin !== self.location.origin')
  expect(codigoWorker).toContain('caminhoApi.test(url.pathname)')
  expect(codigoWorker).toContain('/^\\/api(?:\\/|$)/')
  expect(codigoWorker).toContain('denylist: [/^\\/api\\//]')
  expect(codigoWorkerEmUmaLinha).toMatch(
    /registerRoute\(\s*\(\{\s*request,\s*url\s*\}\)\s*=>\s*request\.method\s*!==\s*['"]GET['"]\s*\|\|\s*url\.origin\s*!==\s*self\.location\.origin\s*\|\|\s*caminhoApi\.test\(url\.pathname\),\s*new NetworkOnly\(\),?\s*\)/,
  )
  expect(codigoWorker).toContain("matchPrecache('/index.html')")
  expect(codigoWorker).toMatch(/fetch\(request\)[\s\S]*?matchPrecache\('\/index\.html'\)/)
  expect(codigoWorker).toContain("setCacheNameDetails({ prefix: 'trapsight' })")
  expect(codigoWorker).toContain('cleanupOutdatedCaches()')
  expect(codigoWorker).not.toMatch(/new (?:CacheFirst|NetworkFirst|StaleWhileRevalidate)\(/)
  expect(codigoWorker).not.toMatch(/\b(?:skipWaiting|clientsClaim)\s*\(/)
})
