import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import EvolucaoGrafico from './EvolucaoGrafico'

describe('EvolucaoGrafico', () => {
  it('expõe a descrição acessível e aceita uma série externa', () => {
    render(
      <EvolucaoGrafico
        resumo="Evolução da cobertura: 1 medição, de 42,00% a 42,00%"
        serie={[{ instante: Date.parse('2026-10-16T08:00:00Z'), percentual: 42 }]}
      />,
    )

    expect(
      screen.getByRole('img', {
        name: 'Evolução da cobertura: 1 medição, de 42,00% a 42,00%',
      }),
    ).toBeVisible()
  })

  it('aceita um marcador temporal opcional', () => {
    render(
      <EvolucaoGrafico
        marcador={Date.parse('2026-10-16T08:00:00Z')}
        resumo="Evolução da cobertura: 1 medição, de 42,00% a 42,00%"
        serie={[{ instante: Date.parse('2026-10-16T08:00:00Z'), percentual: 42 }]}
      />,
    )

    expect(screen.getByRole('img')).toHaveAttribute(
      'aria-label',
      'Evolução da cobertura: 1 medição, de 42,00% a 42,00%',
    )
  })

  it('aceita eventos de seleção e marcas de troca mantendo a descrição acessível', () => {
    render(
      <EvolucaoGrafico
        marcasDeTroca={[Date.parse('2026-09-01T00:00:00Z')]}
        marcador={Date.parse('2026-10-16T08:00:00Z')}
        onInteracaoManual={vi.fn()}
        onMarcadorChange={vi.fn()}
        resumo="Evolução completa da cobertura"
        serie={[{ instante: Date.parse('2026-10-16T08:00:00Z'), percentual: 42 }]}
      />,
    )

    expect(screen.getByRole('img', { name: 'Evolução completa da cobertura' })).toBeVisible()
  })
})
