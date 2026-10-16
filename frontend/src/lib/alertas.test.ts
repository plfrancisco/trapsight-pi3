import { describe, expect, it } from 'vitest'
import { calculateDiasEmAlerta } from './alertas'

describe('calculateDiasEmAlerta', () => {
  const referencia = new Date('2026-10-14T12:00:00Z')

  it('calcula zero, um ou vários dias completos', () => {
    expect(calculateDiasEmAlerta('2026-10-14T08:00:00Z', referencia)).toBe(0)
    expect(calculateDiasEmAlerta('2026-10-13T11:59:59Z', referencia)).toBe(1)
    expect(calculateDiasEmAlerta('2026-10-11T11:59:59Z', referencia)).toBe(3)
  })

  it('limita a zero os inícios que ainda estão no futuro', () => {
    expect(calculateDiasEmAlerta('2026-10-15T08:00:00Z', referencia)).toBe(0)
  })
})
