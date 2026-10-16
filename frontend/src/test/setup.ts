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

afterEach(() => cleanup())
