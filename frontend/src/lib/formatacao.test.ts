import { describe, expect, it } from 'vitest'
import {
  formatData,
  formatDataHora,
  formatDiasAteSaturar,
  formatPercentual,
  rotuloStatus,
} from './formatacao'

describe('formatadores da interface', () => {
  it('formata percentuais, incluindo ausência e valor zero', () => {
    expect(formatPercentual(64.3)).toBe('64,30%')
    expect(formatPercentual(0)).toBe('0,00%')
    expect(formatPercentual(null)).toBe('—')
  })

  it('formata data civil sem deslocamento de fuso e preserva a virada do mês', () => {
    expect(formatData('2026-10-08')).toBe('08/10/2026')
    expect(formatData('2026-03-01')).toBe('01/03/2026')
  })

  it('formata instantes no locale brasileiro e no fuso horário local', () => {
    const instante = '2026-10-08T12:34:00Z'
    expect(formatDataHora(instante)).toBe(
      new Date(instante).toLocaleString('pt-BR', {
        dateStyle: 'short',
        timeStyle: 'short',
      }),
    )
  })

  it('apresenta os limites da estimativa de saturação', () => {
    expect(formatDiasAteSaturar(null)).toBe('Sem estimativa')
    expect(formatDiasAteSaturar(0)).toBe('Trocar agora')
    expect(formatDiasAteSaturar(1)).toBe('1 dia')
    expect(formatDiasAteSaturar(4)).toBe('4 dias')
  })

  it('traduz o status para o rótulo acessível', () => {
    expect(rotuloStatus('ok')).toBe('OK')
    expect(rotuloStatus('atencao')).toBe('Atenção')
    expect(rotuloStatus('trocar')).toBe('Trocar')
  })
})
