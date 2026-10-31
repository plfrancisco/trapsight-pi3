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
      screen.getByRole('group', {
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

    expect(screen.getByRole('group')).toHaveAttribute(
      'aria-label',
      'Evolução da cobertura: 1 medição, de 42,00% a 42,00%',
    )
  })

  it('aceita seleção e mantém a descrição acessível', () => {
    render(
      <EvolucaoGrafico
        marcador={Date.parse('2026-10-16T08:00:00Z')}
        onMarcadorChange={vi.fn()}
        resumo="Evolução completa da cobertura"
        serie={[{ instante: Date.parse('2026-10-16T08:00:00Z'), percentual: 42 }]}
      />,
    )

    expect(screen.getByRole('group', { name: 'Evolução completa da cobertura' })).toBeVisible()
  })

  it('descreve a previsão pelo limiar de troca, sem percentual fixo', () => {
    render(
      <EvolucaoGrafico
        previsaoTroca={{ inicio: Date.parse('2026-11-01T00:00:00Z'), fim: Date.parse('2026-12-01T00:00:00Z'), rotulo: 'Novembro de 2026' }}
        resumo="Evolução da cobertura: 1 medição, de 42,00% a 42,00%"
        serie={[{ instante: Date.parse('2026-10-16T08:00:00Z'), percentual: 42 }]}
      />,
    )

    expect(screen.getByText('Estimativa ao atingir o limiar de troca')).toBeVisible()
    expect(screen.queryByText(/70\s*%/)).not.toBeInTheDocument()
  })
})
