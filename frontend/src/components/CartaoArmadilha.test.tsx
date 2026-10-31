import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import CartaoArmadilha from './CartaoArmadilha'
import type { ArmadilhaLista } from '../services/tipos'

const armadilhaBase: ArmadilhaLista = {
  id: 'arm-1',
  identificador: 'ARM-001',
  localizacao: 'Depósito',
  modelo: 'StickFly K-45',
  modelo_id: null,
  refil_ativo: { id: 'refil-1', data_instalacao: '2026-10-01', dias_em_uso: 13 },
  percentual_atual: 64.3,
  status: 'atencao',
  dias_ate_saturar: null,
  limiar_trocar: 20,
  ultima_analise_em: '2026-10-14T08:00:00Z',
  em_alerta_desde: null,
}

const renderCartao = (armadilha: ArmadilhaLista) =>
  render(
    <MemoryRouter>
      <CartaoArmadilha armadilha={armadilha} />
    </MemoryRouter>,
  )

describe('CartaoArmadilha', () => {
  it('mostra a medição da API, o status, a estimativa e a data da análise', () => {
    renderCartao(armadilhaBase)

    expect(screen.getByText('64,30%')).toBeVisible()
    expect(screen.getByText('Atenção')).toBeVisible()
    expect(screen.getByText('Atenção').closest('dl')).toBeNull()
    expect(screen.getByText('Sem estimativa')).toBeVisible()
    expect(screen.getByText(/Última análise/)).toBeVisible()
    expect(screen.getByRole('link', { name: 'Ver detalhes da armadilha ARM-001' })).toHaveAttribute(
      'href',
      '/armadilhas/arm-1',
    )
  })

  it('não mostra percentual nem estimativa quando não há refil ativo', () => {
    renderCartao({
      ...armadilhaBase,
      refil_ativo: null,
      percentual_atual: null,
      status: null,
      dias_ate_saturar: null,
      limiar_trocar: 20,
      ultima_analise_em: null,
    })

    expect(screen.getByText('Sem refil ativo')).toBeVisible()
    expect(screen.queryByText('Cobertura atual')).not.toBeInTheDocument()
    expect(screen.queryByText('Sem estimativa')).not.toBeInTheDocument()
    expect(screen.queryByText('Atenção')).not.toBeInTheDocument()
  })

  it('indica ausência de análises sem exibir percentual', () => {
    renderCartao({
      ...armadilhaBase,
      percentual_atual: null,
      status: null,
      dias_ate_saturar: null,
      limiar_trocar: 20,
      ultima_analise_em: null,
    })

    expect(screen.getByText('Sem análises neste refil')).toBeVisible()
    expect(screen.queryByText('Estimativa: Sem estimativa')).not.toBeInTheDocument()
    expect(screen.queryByText('Cobertura atual')).not.toBeInTheDocument()
  })
})
