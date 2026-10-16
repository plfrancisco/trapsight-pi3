import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import ResumoArmadilha from './ResumoArmadilha'
import type { ArmadilhaDetalhe } from '../services/tipos'

const armadilha: ArmadilhaDetalhe = {
  id: 'arm-1',
  identificador: 'ARM-001',
  modelo: 'StickFly K-45',
  localizacao: 'Área de recebimento',
  data_instalacao: '2026-06-15',
  refil_ativo: null,
  refis_anteriores: [],
  percentual_atual: null,
  status: null,
  dias_ate_saturar: null,
}

describe('ResumoArmadilha', () => {
  it('apresenta os dados da armadilha e os links de ação', () => {
    render(
      <MemoryRouter>
        <ResumoArmadilha armadilha={armadilha} />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: 'ARM-001', level: 1 })).toBeVisible()
    expect(screen.getByText('StickFly K-45')).toBeVisible()
    expect(screen.getByText('Área de recebimento')).toBeVisible()
    expect(screen.getByText('15/06/2026')).toBeVisible()
    expect(screen.getByRole('link', { name: 'Editar armadilha' })).toHaveAttribute(
      'href',
      '/armadilhas/arm-1/editar',
    )
    expect(screen.getByRole('link', { name: 'Nova análise' })).toHaveAttribute(
      'href',
      '/analises/nova',
    )
  })
})
