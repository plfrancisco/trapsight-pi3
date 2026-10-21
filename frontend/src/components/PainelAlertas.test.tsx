import { render, screen } from '@testing-library/react'
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
  dias_ate_saturar: 0,
  ultima_analise_em: '2026-10-14T08:00:00Z',
  em_alerta_desde: dados.em_alerta_desde ?? null,
})

describe('PainelAlertas', () => {
  it('mantém uma confirmação explícita quando não há armadilhas em alerta', () => {
    render(
      <MemoryRouter>
        <PainelAlertas
          armadilhas={[]}
          carregando={false}
          erro={false}
          instanteReferencia={instanteReferencia}
        />
      </MemoryRouter>,
    )

    expect(screen.getByText('0 armadilhas precisam de ação')).toBeVisible()
    expect(screen.getByText('Nenhuma ação é necessária neste momento.')).toBeVisible()
  })

  it('lista só casos de troca, com localização, duração e link para o detalhe', () => {
    render(
      <MemoryRouter>
        <PainelAlertas
          armadilhas={[
            buildArmadilha({
              id: 'arm-1',
              identificador: 'ARM-001',
              localizacao: 'Depósito',
              em_alerta_desde: '2026-10-12T10:00:00Z',
            }),
            buildArmadilha({
              id: 'arm-2',
              identificador: 'ARM-002',
              localizacao: 'Recebimento',
              status: 'atencao',
              em_alerta_desde: null,
            }),
          ]}
          carregando={false}
          erro={false}
          instanteReferencia={instanteReferencia}
        />
      </MemoryRouter>,
    )

    expect(screen.getByText('1 armadilha precisa de ação')).toBeVisible()
    expect(screen.getByText('Depósito')).toBeVisible()
    expect(screen.getByText('Em alerta há 2 dias')).toBeVisible()
    expect(screen.getByRole('link', { name: 'Ver detalhes da armadilha ARM-001' })).toHaveAttribute(
      'href',
      '/armadilhas/arm-1',
    )
    expect(screen.queryByText('ARM-002')).not.toBeInTheDocument()
  })

  it('escreve hoje quando a armadilha entrou em alerta há zero dias', () => {
    render(
      <MemoryRouter>
        <PainelAlertas
          armadilhas={[
            buildArmadilha({
              id: 'arm-1',
              identificador: 'ARM-001',
              em_alerta_desde: '2026-10-14T12:00:00Z',
            }),
          ]}
          carregando={false}
          erro={false}
          instanteReferencia={instanteReferencia}
        />
      </MemoryRouter>,
    )

    expect(screen.getByText('Em alerta desde hoje')).toBeVisible()
  })
})
