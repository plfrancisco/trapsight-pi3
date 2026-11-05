import { afterEach, expect, it, vi } from 'vitest'
import { registrarServiceWorker } from './registrarServiceWorker'

let descritorServiceWorker: PropertyDescriptor | undefined

afterEach(() => {
  vi.unstubAllEnvs()
  if (descritorServiceWorker) {
    Object.defineProperty(navigator, 'serviceWorker', descritorServiceWorker)
  } else {
    Reflect.deleteProperty(navigator, 'serviceWorker')
  }
  descritorServiceWorker = undefined
})

it('não registra o service worker fora de produção', () => {
  vi.stubEnv('PROD', false)
  const register = vi.fn()
  descritorServiceWorker = Object.getOwnPropertyDescriptor(navigator, 'serviceWorker')
  Object.defineProperty(navigator, 'serviceWorker', {
    configurable: true,
    value: { register },
  })

  registrarServiceWorker()
  window.dispatchEvent(new Event('load'))

  expect(register).not.toHaveBeenCalled()
})

it('registra depois do evento load em produção quando há suporte', () => {
  vi.stubEnv('PROD', true)
  const register = vi.fn().mockResolvedValue(undefined)
  descritorServiceWorker = Object.getOwnPropertyDescriptor(navigator, 'serviceWorker')
  Object.defineProperty(navigator, 'serviceWorker', {
    configurable: true,
    value: { register },
  })

  registrarServiceWorker()
  expect(register).not.toHaveBeenCalled()

  window.dispatchEvent(new Event('load'))

  expect(register).toHaveBeenCalledWith('/sw.js', { scope: '/' })
})
