import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA, type VitePWAOptions } from 'vite-plugin-pwa'
import { defineConfig } from 'vitest/config'
import { pwaManifest } from './pwa-manifest.js'

// As navegações devem tentar a rede; o fallback gerado pelo generateSW lê o precache primeiro.
export const pwaOptions = {
  injectRegister: false,
  devOptions: { enabled: false },
  manifest: pwaManifest,
  strategies: 'injectManifest',
  srcDir: '.',
  filename: 'sw.ts',
  scope: '/',
  includeManifestIcons: false,
  injectManifest: {
    globPatterns: ['index.html', 'assets/**/*', 'icons/*.png'],
    minify: false,
  },
} satisfies Partial<VitePWAOptions>

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA(pwaOptions),
  ],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    clearMocks: true,
    // A carga paralela do CI pode alongar a inicialização do jsdom sem alterar o teste.
    testTimeout: 15_000,
    // Valor fixo para que a suíte não dependa do .env da máquina.
    env: { VITE_API_URL: 'http://localhost:8000/api' },
  },
})
