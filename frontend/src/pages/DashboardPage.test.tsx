import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DashboardPage from './DashboardPage'
import type { ArmadilhaLista } from '../services/tipos'

vi.mock('../services/armadilhas', () => ({ listArmadilhas: vi.fn() }))

import { listArmadilhas } from '../services/armadilhas'

const buildArmadilha = (
  dados: Partial<ArmadilhaLista> & Pick<ArmadilhaLista, 'id' | 'identificador'>,
): ArmadilhaLista => ({
  id: dados.id,
  identificador: dados.identificador,
  localizacao: dados.localizacao ?? 'Área de recebimento',
  modelo: null,
  modelo_id: null,
  refil_ativo:
    dados.refil_ativo === undefined
      ? { id: `refil-${dados.id}`, data_instalacao: '2026-10-01', dias_em_uso: 13 }
      : dados.refil_ativo,
  percentual_atual: dados.percentual_atual === undefined ? 42.5 : dados.percentual_atual,
  status: dados.status === undefined ? 'atencao' : dados.status,
  dias_ate_saturar: dados.dias_ate_saturar === undefined ? 5 : dados.dias_ate_saturar,
  ultima_analise_em:
    dados.ultima_analise_em === undefined
      ? '2026-10-14T08:00:00Z'
      : dados.ultima_analise_em,
  em_alerta_desde: dados.em_alerta_desde ?? null,
})

const renderDashboard = () =>
  render(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>,
  )

beforeEach(() => {
  vi.mocked(listArmadilhas).mockReset()
})

describe('DashboardPage', () => {
  it('preserva a ordem recebida da API', async () => {
    vi.mocked(listArmadilhas).mockResolvedValue([
      buildArmadilha({ id: 'arm-1', identificador: 'ARM-TROCAR', status: 'trocar' }),
      buildArmadilha({
        id: 'arm-2',
        identificador: 'ARM-SEM-ANALISE',
        percentual_atual: null,
        status: null,
        dias_ate_saturar: null,
        ultima_analise_em: null,
      }),
      buildArmadilha({ id: 'arm-3', identificador: 'ARM-ATENCAO', status: 'atencao' }),
    ])
    renderDashboard()

    await screen.findByRole('heading', { name: 'ARM-ATENCAO', level: 3 })
    const identificadores = screen
      .getAllByRole('article')
      .map((artigo) => within(artigo).getByRole('heading', { level: 3 }).textContent)
    expect(identificadores).toEqual([
      'ARM-TROCAR',
      'ARM-SEM-ANALISE',
      'ARM-ATENCAO',
    ])
  })

  it('mantém o painel de alertas visível durante o carregamento', () => {
    vi.mocked(listArmadilhas).mockImplementation(() => new Promise(() => undefined))
    renderDashboard()

    expect(screen.getByRole('heading', { name: 'Alertas de troca' })).toBeVisible()
    expect(screen.getByText('Consultando alertas…')).toBeVisible()
  })

  it('mostra uma ação de cadastro quando a lista está vazia', async () => {
    vi.mocked(listArmadilhas).mockResolvedValue([])
    renderDashboard()

    expect(await screen.findByText('Nenhuma armadilha cadastrada')).toBeVisible()
    expect(
      screen.getByRole('link', { name: 'Cadastrar primeira armadilha' }),
    ).toHaveAttribute('href', '/armadilhas/nova')
    expect(screen.getByText('Nenhuma ação é necessária neste momento.')).toBeVisible()
  })

  it('exibe armadilha sem refil ativo sem percentual ou estimativa', async () => {
    vi.mocked(listArmadilhas).mockResolvedValue([
      buildArmadilha({
        id: 'arm-1',
        identificador: 'ARM-SEM-REFIL',
        refil_ativo: null,
        percentual_atual: null,
        status: null,
        dias_ate_saturar: null,
        ultima_analise_em: null,
      }),
    ])
    renderDashboard()

    const artigo = await screen.findByRole('article')
    expect(within(artigo).getByText('Sem refil ativo')).toBeVisible()
    expect(within(artigo).queryByText('Cobertura atual')).not.toBeInTheDocument()
    expect(within(artigo).queryByText('Sem estimativa')).not.toBeInTheDocument()
  })

  it('indica armadilha com refil ativo e nenhuma análise sem mostrar percentual', async () => {
    vi.mocked(listArmadilhas).mockResolvedValue([
      buildArmadilha({
        id: 'arm-1',
        identificador: 'ARM-SEM-ANALISE',
        percentual_atual: null,
        status: null,
        dias_ate_saturar: null,
        ultima_analise_em: null,
      }),
    ])
    renderDashboard()

    const artigo = await screen.findByRole('article')
    expect(within(artigo).getByText('Sem análises')).toBeVisible()
    expect(within(artigo).queryByText('Estimativa: Sem estimativa')).not.toBeInTheDocument()
    expect(within(artigo).queryByText('Cobertura atual')).not.toBeInTheDocument()
  })

  it('formata estimativa ausente para uma armadilha com uma medição', async () => {
    vi.mocked(listArmadilhas).mockResolvedValue([
      buildArmadilha({ id: 'arm-1', identificador: 'ARM-UMA-MEDICAO', dias_ate_saturar: null }),
    ])
    renderDashboard()

    const artigo = await screen.findByRole('article')
    expect(within(artigo).getByText('Sem estimativa')).toBeVisible()
    expect(within(artigo).getByText('42,50%')).toBeVisible()
  })

  it('permite repetir o carregamento depois de uma falha', async () => {
    vi.mocked(listArmadilhas)
      .mockRejectedValueOnce(new Error('falha interna'))
      .mockResolvedValueOnce([
        buildArmadilha({ id: 'arm-1', identificador: 'ARM-RECUPERADA' }),
      ])
    renderDashboard()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Não foi possível carregar as armadilhas.',
    )
    fireEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }))

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'ARM-RECUPERADA' })).toBeVisible(),
    )
    expect(listArmadilhas).toHaveBeenCalledTimes(2)
  })
})
