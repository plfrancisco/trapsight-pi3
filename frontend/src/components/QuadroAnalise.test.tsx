import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import QuadroAnalise from './QuadroAnalise'
import type { Analise } from '../services/tipos'

const analise: Analise = {
  id: 'analise-1',
  refil_id: 'refil-1',
  armadilha_id: 'armadilha-1',
  analisado_em: '2026-10-16T08:00:00Z',
  percentual_coberto: 42.5,
  status: 'atencao',
  modelo_versao: '1.0.0',
  imagem_url: '/imagem',
}

describe('QuadroAnalise', () => {
  it('exibe os dados, a identificação do modelo e a leitura acessível do quadro', () => {
    render(
      <QuadroAnalise analise={analise} indice={1} quantidade={3} />,
    )

    expect(screen.getByRole('heading', { name: 'Análise 02' })).toBeVisible()
    expect(screen.getByText('100,00%')).toBeVisible()
    expect(screen.getByText('Atenção')).toBeVisible()
    expect(
      screen.getByRole('img', { name: /Imagem com a máscara do modelo da análise/ }),
    ).toHaveAttribute('src', 'http://localhost:8000/api/analises/analise-1/mascara')
    expect(screen.queryByRole('button', { name: 'Ver foto original' })).not.toBeInTheDocument()
    expect(screen.getByText(/Quadro 2 de 3/, { selector: 'p' })).toHaveAttribute(
      'aria-live',
      'polite',
    )
  })
})
