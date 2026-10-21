import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  assinarSessaoExpirada,
  definirCsrf,
  limparCsrf,
  notificarSessaoExpirada,
  obterCsrf,
} from './sessao'

afterEach(() => {
  limparCsrf()
  localStorage.clear()
  sessionStorage.clear()
})

describe('token CSRF em memória', () => {
  it('guarda, devolve e esquece o token', () => {
    expect(obterCsrf()).toBeNull()
    definirCsrf('token-1')
    expect(obterCsrf()).toBe('token-1')
    limparCsrf()
    expect(obterCsrf()).toBeNull()
  })

  it('nunca grava o token em localStorage nem em sessionStorage', () => {
    definirCsrf('token-secreto')

    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
    expect(JSON.stringify({ ...localStorage, ...sessionStorage })).not.toContain('token-secreto')
  })
})

describe('aviso de sessão expirada', () => {
  it('chama os ouvintes registrados', () => {
    const a = vi.fn()
    const b = vi.fn()
    const cancelarA = assinarSessaoExpirada(a)
    const cancelarB = assinarSessaoExpirada(b)

    notificarSessaoExpirada()

    expect(a).toHaveBeenCalledTimes(1)
    expect(b).toHaveBeenCalledTimes(1)
    cancelarA()
    cancelarB()
  })

  it('deixa de chamar um ouvinte depois de cancelado', () => {
    const ouvinte = vi.fn()
    const cancelar = assinarSessaoExpirada(ouvinte)
    cancelar()

    notificarSessaoExpirada()

    expect(ouvinte).not.toHaveBeenCalled()
  })

  it('um ouvinte que se cancela durante o aviso não atrapalha os outros', () => {
    const segundo = vi.fn()
    const cancelarPrimeiro = assinarSessaoExpirada(() => cancelarPrimeiro())
    const cancelarSegundo = assinarSessaoExpirada(segundo)

    notificarSessaoExpirada()

    expect(segundo).toHaveBeenCalledTimes(1)
    cancelarSegundo()
  })
})
