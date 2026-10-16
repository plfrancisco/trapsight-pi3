import { describe, expect, it } from 'vitest'
import { localDateIso } from './datas'

describe('localDateIso', () => {
  it('mantém o dia local para um instante às 23:30', () => {
    const instante = new Date(2026, 9, 16, 23, 30)

    expect(instante.getHours()).toBe(23)
    expect(instante.getMinutes()).toBe(30)
    expect(localDateIso(instante)).toBe('2026-10-16')
  })
})
