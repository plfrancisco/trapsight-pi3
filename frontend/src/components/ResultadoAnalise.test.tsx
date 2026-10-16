import { render, screen } from '@testing-library/react'
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
  mascara_url: '/api/analises/analise-1/mascara',
}

describe('ResultadoAnalise', () => {
  it('exibe o resultado da API e reserva espaço acessível para as duas imagens', () => {
    render(<ResultadoAnalise analise={analise} />)

    expect(screen.getByText('64,30%')).toBeVisible()
    expect(screen.getByText('Atenção')).toBeVisible()
    expect(screen.getByText('v1.2.0+a3f9c2e1')).toBeVisible()
    expect(
      screen.getByRole('img', {
        name: 'Imagem original enviada para análise da armadilha',
      }),
    ).toHaveAttribute('width', '640')
    expect(
      screen.getByRole('img', {
        name: 'Imagem da armadilha com a máscara de segmentação sobreposta',
      }),
    ).toHaveAttribute('height', '480')
  })
})
