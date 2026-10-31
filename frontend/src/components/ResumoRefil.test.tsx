import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ResumoRefil from './ResumoRefil'

describe('ResumoRefil', () => {
  it('apresenta os valores atuais enviados pela API', () => {
    render(
      <ResumoRefil
        diasAteSaturar={4}
        percentualAtual={64.3}
        refil={{ id: 'refil-1', data_instalacao: '2026-08-01', dias_em_uso: 20 }}
        status="atencao"
      />,
    )

    expect(screen.getByText('01/08/2026')).toBeVisible()
    expect(screen.getByText('20 dias')).toBeVisible()
    expect(screen.getByText('64,30%')).toBeVisible()
    expect(screen.getByText('4 dias')).toBeVisible()
    expect(screen.getByText('Atenção')).toBeVisible()
  })

  it('orienta a registrar um refil sem exibir cobertura quando não há ciclo ativo', () => {
    render(
      <ResumoRefil
        diasAteSaturar={null}
        percentualAtual={null}
        refil={null}
        status={null}
      />,
    )

    expect(screen.getByText(/Sem refil ativo/)).toBeVisible()
    expect(screen.queryByText('Cobertura atual')).not.toBeInTheDocument()
    expect(screen.queryByText(/%/)).not.toBeInTheDocument()
  })

  it('mantém os valores em duas colunas para não se sobreporem no cartão estreito', () => {
    const { container } = render(
      <ResumoRefil
        diasAteSaturar={4}
        percentualAtual={64.3}
        refil={{ id: 'refil-1', data_instalacao: '2026-08-01', dias_em_uso: 20 }}
        status="atencao"
      />,
    )

    const lista = container.querySelector('dl')
    expect(lista).toHaveClass('grid-cols-2')
    expect(lista?.className).not.toMatch(/grid-cols-4/)
  })
})
