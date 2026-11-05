import { cleanup } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'

if (!HTMLDialogElement.prototype.showModal) {
  // jsdom não implementa o ciclo modal completo do navegador.
  HTMLDialogElement.prototype.showModal = function showModal() {
    this.setAttribute('open', '')
  }

  HTMLDialogElement.prototype.close = function close() {
    if (!this.open) return
    this.removeAttribute('open')
    this.dispatchEvent(new Event('close'))
  }
}

globalThis.ResizeObserver = class implements ResizeObserver {
  constructor(callback: ResizeObserverCallback) {
    void callback
  }

  observe(target: Element): void {
    void target
  }

  unobserve(target: Element): void {
    void target
  }

  disconnect(): void {
    return
  }
}

afterEach(() => {
  cleanup()
  // O cache local e a marca de atividade não podem vazar de um teste para o seguinte.
  try {
    window.localStorage.clear()
    window.sessionStorage.clear()
  } catch {
    // Testes que trocam o armazenamento por um que falha restauram o original sozinhos.
  }
})
