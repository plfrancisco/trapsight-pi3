import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import BarraProgressoAnalise from './BarraProgressoAnalise'

describe('BarraProgressoAnalise', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('começa em 0% na fase de envio, com os atributos de acessibilidade', () => {
    render(<BarraProgressoAnalise concluido={false} />)

    const barra = screen.getByRole('progressbar', { name: 'Progresso da análise' })
    expect(barra).toHaveAttribute('aria-valuemin', '0')
    expect(barra).toHaveAttribute('aria-valuemax', '100')
    expect(barra).toHaveAttribute('aria-valuenow', '0')
    expect(screen.getByRole('status')).toHaveTextContent('Enviando a foto…')
  })

  it('passa à fase de medição e avança sem chegar a 100% enquanto espera', () => {
    render(<BarraProgressoAnalise concluido={false} />)

    act(() => {
      vi.advanceTimersByTime(3000)
    })

    const barra = screen.getByRole('progressbar')
    const valor = Number(barra.getAttribute('aria-valuenow'))
    expect(valor).toBeGreaterThan(15)
    expect(valor).toBeLessThan(100)
    expect(screen.getByRole('status')).toHaveTextContent('O modelo está medindo a saturação…')
  })

  it('vai a 100% e mostra "Análise concluída" quando termina', () => {
    const { rerender } = render(<BarraProgressoAnalise concluido={false} />)
    act(() => {
      vi.advanceTimersByTime(1500)
    })

    rerender(<BarraProgressoAnalise concluido />)

    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100')
    expect(screen.getByRole('status')).toHaveTextContent('Análise concluída')
    expect(screen.getByText('100%')).toBeInTheDocument()
  })
})
