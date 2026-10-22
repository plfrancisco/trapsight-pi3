import { describe, expect, it } from 'vitest'
import { LIMIAR_ATENCAO, LIMIAR_TROCAR } from './limiares'

describe('limiares de apresentação', () => {
  it('espelha os valores configurados no backend', () => {
    expect(LIMIAR_ATENCAO).toBe(10)
    expect(LIMIAR_TROCAR).toBe(20)
  })
})
