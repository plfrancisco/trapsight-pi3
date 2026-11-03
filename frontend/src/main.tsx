import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './config'
import './index.css'
import App from './App.tsx'
import { configurarFavicon } from './lib/favicon'

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

const corDaBarra = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')
if (corDaBarra) corDaBarra.content = temaSalvo === 'escuro' ? '#0a1316' : '#f5f7f6'

configurarFavicon()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
