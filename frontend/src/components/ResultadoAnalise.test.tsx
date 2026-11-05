import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ResultadoAnalise from './ResultadoAnalise'
import type { Analise } from '../services/tipos'

const analise: Analise = {
  id: 'analise-1',
  refil_id: 'refil-1',
  armadilha_id: 'arm-1',
  analisado_em: '2026-10-14T12:00:00Z',
  percentual_coberto: 64.3,
  status: 'atencao',
  modelo_versao: 'v1.2.0+a3f9c2e1',
  imagem_url: '/api/analises/analise-1/imagem',
}

describe('ResultadoAnalise', () => {
  it('exibe o resultado da API e a imagem com a máscara do modelo', () => {
    render(<ResultadoAnalise analise={analise} />)

    expect(screen.getByText('100,00%')).toBeVisible()
    expect(screen.getByText('64,30% da placa coberta')).toBeVisible()
    expect(screen.getByText('Saturação do refil')).toBeVisible()
    expect(screen.getByText('Atenção')).toBeVisible()
    expect(screen.getByText('v1.2.0+a3f9c2e1')).toBeVisible()
    const imagem = screen.getByRole('img', {
      name: 'Imagem com a máscara do modelo enviada para análise da armadilha',
    })
    expect(imagem).toHaveAttribute('width', '640')
    expect(imagem).toHaveAttribute(
      'src',
      'http://localhost:8000/api/analises/analise-1/mascara',
    )
    expect(
      screen.getByText('Área coberta da placa, marcada pelo modelo'),
    ).toBeVisible()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('volta para a foto original quando a máscara não carrega', () => {
    render(<ResultadoAnalise analise={analise} />)

    fireEvent.error(
      screen.getByRole('img', { name: /Imagem com a máscara do modelo/ }),
    )

    expect(
      screen.getByRole('img', { name: 'Imagem original enviada para análise da armadilha' }),
    ).toHaveAttribute('src', 'http://localhost:8000/api/analises/analise-1/imagem')
    expect(
      screen.queryByText('Área coberta da placa, marcada pelo modelo'),
    ).not.toBeInTheDocument()
  })

  it('converte a cobertura real em saturação sem esconder o valor medido', () => {
    render(<ResultadoAnalise analise={{ ...analise, percentual_coberto: 12.5 }} />)

    expect(screen.getByText('50,00%')).toBeVisible()
    expect(screen.getByText('12,50% da placa coberta')).toBeVisible()
  })
})
