import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ListaRefisAnteriores from './ListaRefisAnteriores'

describe('ListaRefisAnteriores', () => {
  it('lista datas e duração de cada ciclo encerrado', () => {
    render(
      <ListaRefisAnteriores
        refis={[
          {
            id: 'refil-antigo',
            data_instalacao: '2026-06-15',
            data_troca: '2026-07-31',
            dias_ate_troca: 46,
          },
        ]}
      />,
    )

    expect(screen.getByRole('heading', { name: 'Refis anteriores' })).toBeVisible()
    expect(screen.getByText('15/06/2026 – 31/07/2026')).toBeVisible()
    expect(screen.getByText('46 dias de uso')).toBeVisible()
  })

  it('não renderiza uma seção de histórico vazia', () => {
    render(<ListaRefisAnteriores refis={[]} />)

    expect(screen.queryByRole('heading', { name: 'Refis anteriores' })).not.toBeInTheDocument()
  })
})
