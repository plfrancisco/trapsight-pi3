import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { pwaManifest } from './pwa-manifest'

const diretorioFrontend = dirname(fileURLToPath(import.meta.url))

function caminhoIconePublico(src: string): string {
  return resolve(diretorioFrontend, 'public', src.replace(/^\/+/, ''))
}

describe('manifesto e metadados da PWA', () => {
  it('declara os campos necessários para identificar e abrir o aplicativo', () => {
    const manifesto = JSON.parse(JSON.stringify(pwaManifest)) as typeof pwaManifest

    expect(manifesto).toMatchObject({
      name: 'TrapSight',
      short_name: 'TrapSight',
      description: expect.any(String),
      lang: 'pt-BR',
      start_url: '/',
      scope: '/',
      display: 'standalone',
      theme_color: '#0a5c66',
      background_color: '#f5f7f6',
    })
    expect(manifesto.description.trim().length).toBeGreaterThan(0)
  })

  it('aponta para os ícones PNG presentes em public', () => {
    const icone192 = pwaManifest.icons.find((icone) => icone.sizes === '192x192')
    const icone512 = pwaManifest.icons.find(
      (icone) => icone.sizes === '512x512' && icone.purpose === 'any',
    )
    const iconeMascara = pwaManifest.icons.find(
      (icone) => icone.sizes === '512x512' && icone.purpose === 'maskable',
    )

    expect(icone192).toMatchObject({ type: 'image/png', purpose: 'any' })
    expect(icone512).toMatchObject({ type: 'image/png', purpose: 'any' })
    expect(iconeMascara).toMatchObject({ type: 'image/png', purpose: 'maskable' })

    for (const icone of pwaManifest.icons) {
      expect(existsSync(caminhoIconePublico(icone.src)), icone.src).toBe(true)
    }
    expect(existsSync(caminhoIconePublico('/icons/apple-touch-icon.png'))).toBe(true)
  })

  it('declara o ícone da Apple e as cores dos temas no HTML', () => {
    const html = readFileSync(resolve(diretorioFrontend, 'index.html'), 'utf8')

    expect(html).toContain('<link rel="apple-touch-icon" href="/icons/apple-touch-icon.png"')
    expect(html).toContain('name="theme-color" content="#f5f7f6" media="(prefers-color-scheme: light)"')
    expect(html).toContain('name="theme-color" content="#0a1316" media="(prefers-color-scheme: dark)"')
  })
})
