import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import QuadroTimelapse from './QuadroTimelapse'
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
  mascara_url: '/mascara',
}

describe('QuadroTimelapse', () => {
  it('exibe os dados, a imagem original e a leitura acessível do quadro', () => {
    render(
      <QuadroTimelapse analise={analise} indice={1} quantidade={3} />,
    )

    expect(screen.getByRole('heading', { name: 'Análise 02' })).toBeVisible()
    expect(screen.getByText('42,50%')).toBeVisible()
    expect(screen.getByText('Atenção')).toBeVisible()
    expect(screen.getByRole('img', { name: /Imagem original da análise/ })).toHaveAttribute(
      'src',
      'http://localhost:8000/api/analises/analise-1/imagem',
    )
    expect(screen.queryByRole('img', { name: /Máscara da análise/ })).not.toBeInTheDocument()
    expect(screen.getByText(/Quadro 2 de 3/, { selector: 'p' })).toHaveAttribute(
      'aria-live',
      'polite',
    )
  })
})
