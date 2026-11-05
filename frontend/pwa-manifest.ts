import type { ManifestOptions } from 'vite-plugin-pwa'

/** Metadados públicos usados pelo plugin para gerar o manifesto da aplicação. */
export const pwaManifest = {
  name: 'TrapSight',
  short_name: 'TrapSight',
  description: 'Monitore armadilhas adesivas e acompanhe as análises.',
  lang: 'pt-BR',
  start_url: '/',
  scope: '/',
  display: 'standalone',
  theme_color: '#0a5c66',
  background_color: '#f5f7f6',
  icons: [
    {
      src: '/icons/icon-192.png',
      sizes: '192x192',
      type: 'image/png',
      purpose: 'any',
    },
    {
      src: '/icons/icon-512.png',
      sizes: '512x512',
      type: 'image/png',
      purpose: 'any',
    },
    {
      src: '/icons/icon-maskable-512.png',
      sizes: '512x512',
      type: 'image/png',
      purpose: 'maskable',
    },
  ],
} satisfies Partial<ManifestOptions>
