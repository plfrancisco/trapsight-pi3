import { describe, expect, it } from 'vitest'
import { destinoDoEstado, destinoSeguro } from './destino'

describe('destinoSeguro', () => {
  it.each([
    ['/', '/'],
    ['/armadilhas/abc', '/armadilhas/abc'],
    ['/armadilhas/abc?x=1#topo', '/armadilhas/abc?x=1#topo'],
    ['/analises/nova', '/analises/nova'],
  ])('mantém o caminho interno %s', (entrada, esperado) => {
    expect(destinoSeguro(entrada)).toBe(esperado)
  })

  it.each([
    ['endereço absoluto', 'https://invasor.example/'],
    ['sem esquema (protocolo relativo)', '//invasor.example'],
    ['barra invertida', '/\\invasor.example'],
    ['barra e barra invertida', '\\/invasor.example'],
    ['esquema javascript', 'javascript:alert(1)'],
    ['esquema data', 'data:text/html,<script>alert(1)</script>'],
    ['sem barra inicial', 'armadilhas/abc'],
    ['vazio', ''],
    ['caractere de controle', '/ok\nhttps://invasor.example'],
    ['tabulação', '/\tinvasor'],
  ])('recusa %s e usa o padrão', (_motivo, entrada) => {
    expect(destinoSeguro(entrada)).toBe('/')
  })

  it('recusa valores que não são texto', () => {
    expect(destinoSeguro(undefined)).toBe('/')
    expect(destinoSeguro(null)).toBe('/')
    expect(destinoSeguro(42)).toBe('/')
    expect(destinoSeguro({ destino: '/x' })).toBe('/')
  })

  it('não devolve o próprio login, para não criar laço', () => {
    expect(destinoSeguro('/login')).toBe('/')
    expect(destinoSeguro('/login?x=1')).toBe('/')
  })

  it('aceita um padrão diferente', () => {
    expect(destinoSeguro('https://invasor.example', '/inicio')).toBe('/inicio')
  })
})

describe('destinoDoEstado', () => {
  it('lê o destino do estado de navegação', () => {
    expect(destinoDoEstado({ destino: '/armadilhas/abc' })).toBe('/armadilhas/abc')
  })

  it('valida o destino lido', () => {
    expect(destinoDoEstado({ destino: 'https://invasor.example' })).toBe('/')
  })

  it.each([[null], [undefined], ['texto'], [{}], [{ outro: '/x' }], [42]])(
    'usa o padrão para o estado %j',
    (estado) => {
      expect(destinoDoEstado(estado)).toBe('/')
    },
  )
})
