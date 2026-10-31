import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import ResumoArmadilha from './ResumoArmadilha'
import type { ArmadilhaDetalhe } from '../services/tipos'

const armadilha: ArmadilhaDetalhe = {
  id: 'arm-1',
  identificador: 'ARM-001',
  modelo: 'StickFly K-45',
  modelo_id: null,
  localizacao: 'Área de recebimento',
  data_instalacao: '2026-06-15',
  refil_ativo: null,
  refis_anteriores: [],
  percentual_atual: null,
  status: null,
  dias_ate_saturar: null,
  limiar_trocar: 20,
  foto_tipo: 'padrao',
  foto_url: null,
  removida_em: null,
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
    expect(screen.getByRole('button', { name: 'Excluir armadilha' })).toBeVisible()
  })

  it('mantém a consulta do histórico e esconde ações de uma armadilha removida', () => {
    render(
      <MemoryRouter>
        <ResumoArmadilha armadilha={{ ...armadilha, removida_em: '2026-10-21T12:00:00Z' }} />
      </MemoryRouter>,
    )

    expect(screen.getByRole('status')).toHaveTextContent('histórico permanece disponível')
    expect(screen.getByRole('link', { name: 'Voltar ao painel' })).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Excluir armadilha' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Nova análise' })).not.toBeInTheDocument()
  })

  it('mostra a foto padrão do modelo ou a real, conforme o tipo informado', () => {
    const { rerender } = render(
      <MemoryRouter>
        <ResumoArmadilha armadilha={armadilha} />
      </MemoryRouter>,
    )
    expect(screen.getByRole('img', { name: /Foto padrão do modelo/ })).toBeVisible()

    rerender(
      <MemoryRouter>
        <ResumoArmadilha
          armadilha={{ ...armadilha, foto_tipo: 'real', foto_url: '/api/armadilhas/arm-1/foto?v=5' }}
        />
      </MemoryRouter>,
    )
    expect(screen.getByRole('img', { name: 'Foto da armadilha ARM-001' })).toHaveAttribute(
      'src',
      'http://localhost:8000/api/armadilhas/arm-1/foto?v=5',
    )
  })
})
