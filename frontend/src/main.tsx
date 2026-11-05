import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './config'
import './index.css'
import App from './App.tsx'
import { atualizarCorDaBarra } from './lib/corDaBarra'
import { configurarFavicon } from './lib/favicon'
import { registrarServiceWorker } from './lib/registrarServiceWorker'

const temaSalvo = (() => {
  try {
    return window.localStorage.getItem('trapsight:tema') === 'claro'
      ? 'claro'
      : 'escuro'
  } catch {
    return 'escuro'
  }
})()

document.documentElement.dataset.theme = temaSalvo
document.documentElement.style.colorScheme = temaSalvo === 'escuro' ? 'dark' : 'light'
atualizarCorDaBarra(temaSalvo)

configurarFavicon()
registrarServiceWorker()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
