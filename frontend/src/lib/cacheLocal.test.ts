import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  CHAVE_ATIVIDADE,
  VALIDADE_CACHE_MS,
  gravarCache,
  lerCache,
  limparCacheUsuario,
} from './cacheLocal'

const ehLista = (valor: unknown): valor is string[] => Array.isArray(valor)

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-11-05T12:00:00Z'))
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('cacheLocal', () => {
  it('devolve o que foi gravado e nada quando não há registro', () => {
    expect(lerCache('lista')).toBeNull()

    gravarCache('lista', ['a', 'b'])

    expect(lerCache('lista', ehLista)).toEqual(['a', 'b'])
  })

  it('descarta o dado depois de 24 horas', () => {
    gravarCache('lista', ['a'])

    vi.setSystemTime(Date.now() + VALIDADE_CACHE_MS - 1)
    expect(lerCache('lista', ehLista)).toEqual(['a'])

    vi.setSystemTime(Date.now() + 2)
    expect(lerCache('lista', ehLista)).toBeNull()
    expect(window.localStorage.length).toBe(0)
  })

  it('descarta formato inválido e JSON quebrado', () => {
    gravarCache('lista', { nao: 'e lista' })
    expect(lerCache('lista', ehLista)).toBeNull()

    window.localStorage.setItem('trapsight:cache:v1:quebrado', '{não é json')
    expect(lerCache('quebrado')).toBeNull()
  })

  it('ignora um registro gravado por uma versão antiga do formato', () => {
    window.localStorage.setItem(
      'trapsight:cache:v0:lista',
      JSON.stringify({ salvoEm: Date.now(), valor: ['velho'] }),
    )

    expect(lerCache('lista')).toBeNull()
  })

  it('apaga o cache e a marca de atividade, mas preserva preferências', () => {
    gravarCache('sessao', { id: 'u1' })
    gravarCache('armadilhas', ['a'])
    window.localStorage.setItem(CHAVE_ATIVIDADE, String(Date.now()))
    window.localStorage.setItem('tema', 'escuro')
    window.localStorage.setItem('trapsight:convite-instalacao-dispensado', 'true')

    limparCacheUsuario()

    expect(lerCache('sessao')).toBeNull()
    expect(lerCache('armadilhas')).toBeNull()
    expect(window.localStorage.getItem(CHAVE_ATIVIDADE)).toBeNull()
    expect(window.localStorage.getItem('tema')).toBe('escuro')
    expect(window.localStorage.getItem('trapsight:convite-instalacao-dispensado')).toBe('true')
  })

  it('não lança quando o armazenamento está indisponível', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('bloqueado')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('cheio')
    })

    expect(() => gravarCache('lista', ['a'])).not.toThrow()
    expect(lerCache('lista')).toBeNull()
    expect(() => limparCacheUsuario()).not.toThrow()
  })
})
