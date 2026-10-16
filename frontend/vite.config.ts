import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    clearMocks: true,
    // Valor fixo para que a suíte não dependa do .env da máquina.
    env: { VITE_API_URL: 'http://localhost:8000/api' },
  },
})
