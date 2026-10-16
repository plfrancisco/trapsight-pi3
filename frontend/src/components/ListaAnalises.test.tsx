import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ListaAnalises from './ListaAnalises'
import type { Analise } from '../services/tipos'

function buildAnalise(
  id: string,
  analisadoEm: string,
  percentual: number,
  status: Analise['status'],
): Analise {
  return {
    id,
    refil_id: 'refil-1',
    armadilha_id: 'arm-1',
    analisado_em: analisadoEm,
    percentual_coberto: percentual,
    status,
    modelo_versao: '1.0.0',
    imagem_url: `/analises/${id}/imagem`,
    mascara_url: `/analises/${id}/mascara`,
  }
}

describe('ListaAnalises', () => {
  it('lista do mais recente ao mais antigo sem mutar a série da API', () => {
    const analises = [
      buildAnalise('a-1', '2026-10-14T08:00:00Z', 27.5, 'ok'),
      buildAnalise('a-2', '2026-10-16T08:00:00Z', 63.25, 'atencao'),
    ]

    render(<ListaAnalises analises={analises} />)

    const itens = screen.getAllByRole('listitem')
    expect(within(itens[0]).getByText('Cobertura: 63,25%')).toBeVisible()
    expect(within(itens[1]).getByText('Cobertura: 27,50%')).toBeVisible()
    expect(analises.map((analise) => analise.id)).toEqual(['a-1', 'a-2'])

    const miniatura = within(itens[0]).getByRole('img')
    expect(miniatura).toHaveAttribute('loading', 'lazy')
    expect(miniatura).toHaveAttribute('width', '96')
    expect(miniatura).toHaveAttribute('height', '96')
    expect(miniatura).toHaveAccessibleName(/cobertura de 63,25%/)
    expect(within(itens[0]).getByText('Atenção')).toBeVisible()
  })

  it('não exibe uma lista quando ainda não há análises', () => {
    const { container } = render(<ListaAnalises analises={[]} />)

    expect(container).toBeEmptyDOMElement()
  })
})
