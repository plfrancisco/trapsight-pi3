import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import EvolucaoCobertura from './EvolucaoCobertura'
import type { Analise } from '../services/tipos'

function buildAnalise(
  id: string,
  analisadoEm: string,
  percentual: number,
): Analise {
  return {
    id,
    refil_id: 'refil-1',
    armadilha_id: 'armadilha-1',
    analisado_em: analisadoEm,
    percentual_coberto: percentual,
    status: percentual >= 20 ? 'trocar' : percentual >= 10 ? 'atencao' : 'ok',
    modelo_versao: '1.0.0',
    imagem_url: `/analises/${id}/imagem`,
  }
}

const analisesAtivas = [
  buildAnalise('analise-1', '2026-10-01T08:00:00Z', 20),
  buildAnalise('analise-2', '2026-10-05T08:00:00Z', 45),
  buildAnalise('analise-3', '2026-10-10T08:00:00Z', 72),
]

describe('EvolucaoCobertura', () => {
  it('mantém o gráfico interativo e a foto do registro selecionado sem controles de vídeo', async () => {
    render(<EvolucaoCobertura analisesAtivas={analisesAtivas} diasAteSaturar={12} />)

    expect(await screen.findByText('Cobertura medida', {}, { timeout: 15000 })).toBeVisible()
    expect(screen.getByRole('group', { name: /Evolução da cobertura/ })).toBeVisible()
    expect(screen.getByText('Passe o cursor, toque ou use as setas no gráfico para ver a foto daquela data.')).toBeVisible()
    expect(screen.getByRole('img', { name: /Imagem original da análise/ })).toHaveAttribute(
      'src',
      'http://localhost:8000/api/analises/analise-1/imagem',
    )
    expect(screen.queryByRole('group', { name: 'Escopo temporal' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Reproduzir|Pausar/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('slider')).not.toBeInTheDocument()
  }, 30000)

  it('exibe a foto quando há só uma medição', () => {
    render(<EvolucaoCobertura analisesAtivas={[analisesAtivas[0]]} />)

    expect(screen.getByRole('img', { name: /Imagem da armadilha registrada/ })).toBeVisible()
    expect(screen.queryByRole('group', { name: /Evolução da cobertura/ })).not.toBeInTheDocument()
  })

  it('não renderiza conteúdo quando não há análises', () => {
    const { container } = render(<EvolucaoCobertura analisesAtivas={[]} />)

    expect(container).toBeEmptyDOMElement()
  })
})
