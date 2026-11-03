import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import PainelAlertas from './PainelAlertas'
import type { ArmadilhaLista } from '../services/tipos'

const instanteReferencia = new Date('2026-10-14T12:00:00Z')

const buildArmadilha = (
  dados: Partial<ArmadilhaLista> & Pick<ArmadilhaLista, 'id' | 'identificador'>,
): ArmadilhaLista => ({
  id: dados.id,
  identificador: dados.identificador,
  localizacao: dados.localizacao ?? null,
  modelo: null,
  modelo_id: null,
  refil_ativo: { id: 'refil-1', data_instalacao: '2026-10-01', dias_em_uso: 13 },
  percentual_atual: 85,
  status: dados.status ?? 'trocar',
  dias_ate_saturar: dados.dias_ate_saturar ?? 0,
  limiar_trocar: 20,
  foto_tipo: 'padrao',
  foto_url: null,
  ultima_analise_em: '2026-10-14T08:00:00Z',
  em_alerta_desde: dados.em_alerta_desde ?? null,
})

function renderFila(armadilhas: ArmadilhaLista[]) {
  return render(
    <MemoryRouter>
      <PainelAlertas
        armadilhas={armadilhas}
        carregando={false}
        erro={false}
        instanteReferencia={instanteReferencia}
      />
    </MemoryRouter>,
  )
}

describe('Fila de ação', () => {
  it('mostra zero e uma orientação clara quando não há prioridade', () => {
    renderFila([])

    expect(screen.getByText('0 ações')).toBeVisible()
    expect(screen.getByText('Nenhuma ação necessária hoje.')).toBeVisible()
  })

  it('inclui atenção e troca na ordem recebida, com prazo e ação apropriados', () => {
    renderFila([
      buildArmadilha({
        id: 'arm-1',
        identificador: 'ARM-001',
        localizacao: 'Depósito',
        status: 'trocar',
        em_alerta_desde: '2026-10-12T10:00:00Z',
      }),
      buildArmadilha({
        id: 'arm-2',
        identificador: 'ARM-002',
        localizacao: 'Recebimento',
        status: 'atencao',
        dias_ate_saturar: 4,
      }),
      buildArmadilha({ id: 'arm-3', identificador: 'ARM-003', status: 'ok' }),
    ])

    const fila = screen.getByRole('list')
    const identificadores = within(fila).getAllByRole('link', { name: /Ver detalhes da armadilha/ })
    expect(identificadores.map((link) => link.textContent)).toEqual(['ARM-001', 'ARM-002'])
    expect(screen.getByText('2 ações')).toBeVisible()
    expect(screen.getByText('Saturada há 2 dias')).toBeVisible()
    expect(screen.getByText('Satura em 4 dias')).toBeVisible()
    expect(screen.getByRole('link', { name: 'Registrar troca: ARM-001' })).toHaveAttribute(
      'href',
      '/armadilhas/arm-1',
    )
    expect(screen.getByRole('link', { name: 'Ver armadilha: ARM-002' })).toHaveAttribute(
      'href',
      '/armadilhas/arm-2',
    )
    expect(screen.queryByText('ARM-003')).not.toBeInTheDocument()
  })

  it('marca como hoje uma troca que entrou em alerta hoje', () => {
    renderFila([
      buildArmadilha({
        id: 'arm-1',
        identificador: 'ARM-001',
        status: 'trocar',
        em_alerta_desde: '2026-10-14T12:00:00Z',
      }),
    ])

    expect(screen.getByText('Saturada hoje')).toBeVisible()
  })
})
