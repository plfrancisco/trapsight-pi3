import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './config'
import './index.css'
import App from './App.tsx'
import { configurarFavicon } from './lib/favicon'

configurarFavicon()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
