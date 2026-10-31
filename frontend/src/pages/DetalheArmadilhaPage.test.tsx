import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DetalheArmadilhaPage from './DetalheArmadilhaPage'
import type { Analise, ArmadilhaDetalhe } from '../services/tipos'
import { ApiError } from '../services/erros'

vi.mock('../services/armadilhas', () => ({
  getArmadilha: vi.fn(),
  replaceRefil: vi.fn(),
}))
vi.mock('../services/analises', () => ({ listAnalises: vi.fn() }))

import { getArmadilha, replaceRefil } from '../services/armadilhas'
import { listAnalises } from '../services/analises'

function buildArmadilha(
  alteracoes: Partial<ArmadilhaDetalhe> = {},
): ArmadilhaDetalhe {
  return {
    id: 'arm-1',
    identificador: 'ARM-001',
    modelo: 'StickFly K-45',
    modelo_id: 'mod-1',
    localizacao: 'Área de recebimento',
    data_instalacao: '2026-06-15',
    refil_ativo: { id: 'refil-1', data_instalacao: '2026-08-01', dias_em_uso: 20 },
    refis_anteriores: [],
    percentual_atual: 42.5,
    status: 'atencao',
    dias_ate_saturar: 5,
    limiar_trocar: 20,
    ...alteracoes,
  }
}

function buildAnalise(
  id: string,
  analisadoEm: string,
  percentual: number,
): Analise {
  return {
    id,
    refil_id: 'refil-1',
    armadilha_id: 'arm-1',
    analisado_em: analisadoEm,
    percentual_coberto: percentual,
    status: 'atencao',
    modelo_versao: '1.0.0',
    imagem_url: `/analises/${id}/imagem`,
  }
}

function renderDetalhe() {
  return render(
    <MemoryRouter initialEntries={['/armadilhas/arm-1']}>
      <Routes>
        <Route path="/armadilhas/:id" element={<DetalheArmadilhaPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

function mockDetalhe(analises: Analise[] = []) {
  vi.mocked(getArmadilha).mockResolvedValue(buildArmadilha())
  vi.mocked(listAnalises).mockResolvedValue(analises)
}

beforeEach(() => {
  vi.mocked(getArmadilha).mockReset()
  vi.mocked(listAnalises).mockReset()
  vi.mocked(replaceRefil).mockReset()
})

describe('DetalheArmadilhaPage', () => {
  it('mostra o estado de carregamento enquanto as consultas estão pendentes', () => {
    vi.mocked(getArmadilha).mockImplementation(() => new Promise(() => undefined))
    vi.mocked(listAnalises).mockImplementation(() => new Promise(() => undefined))
    renderDetalhe()

    expect(screen.getByRole('status')).toHaveTextContent('Carregando')
  })

  it('carrega armadilha e análises ativas juntas com os parâmetros documentados', async () => {
    mockDetalhe()
    renderDetalhe()

    expect(await screen.findByRole('heading', { name: 'ARM-001', level: 1 })).toBeVisible()
    await waitFor(() => {
      expect(getArmadilha).toHaveBeenCalledWith('arm-1', expect.any(AbortSignal))
      expect(listAnalises).toHaveBeenCalledWith(
        'arm-1',
        { escopo: 'refil_ativo', limite: 1000 },
        expect.any(AbortSignal),
      )
    })
  })

  it('permite repetir o carregamento depois de uma falha', async () => {
    vi.mocked(getArmadilha)
      .mockRejectedValueOnce(new ApiError('FALHA_DE_REDE', 'Falha temporária.', 503))
      .mockResolvedValueOnce(buildArmadilha())
    vi.mocked(listAnalises).mockResolvedValue([])
    renderDetalhe()

    expect(await screen.findByRole('alert')).toHaveTextContent('Falha temporária.')
    fireEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }))

    expect(await screen.findByRole('heading', { name: 'ARM-001', level: 1 })).toBeVisible()
    expect(getArmadilha).toHaveBeenCalledTimes(2)
  })

  it('reutiliza o estado de armadilha não encontrada pelo código da API', async () => {
    vi.mocked(getArmadilha).mockRejectedValue(
      new ApiError('ARMADILHA_NAO_ENCONTRADA', 'Não encontrada.', 404),
    )
    vi.mocked(listAnalises).mockResolvedValue([])
    renderDetalhe()

    expect(await screen.findByRole('heading', { name: 'Armadilha não encontrada' })).toBeVisible()
    expect(screen.getByRole('link', { name: 'Ir para o dashboard' })).toHaveAttribute(
      'href',
      '/',
    )
  })

  it('trata UUID inválida como armadilha ausente', async () => {
    vi.mocked(getArmadilha).mockRejectedValue(
      new ApiError('VALIDACAO_FALHOU', 'UUID inválida.', 422, {
        campos_invalidos: [{ campo: 'armadilha_id', tipo: 'uuid_parsing' }],
      }),
    )
    vi.mocked(listAnalises).mockResolvedValue([])
    renderDetalhe()

    expect(await screen.findByRole('heading', { name: 'Armadilha não encontrada' })).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Tentar novamente' })).not.toBeInTheDocument()
  })

  it('mantém erro genérico para outros códigos HTTP 404', async () => {
    vi.mocked(getArmadilha).mockRejectedValue(
      new ApiError('ROTA_NAO_ENCONTRADA', 'A rota não existe.', 404),
    )
    vi.mocked(listAnalises).mockResolvedValue([])
    renderDetalhe()

    expect(await screen.findByRole('alert')).toHaveTextContent('A rota não existe.')
    expect(screen.getByRole('button', { name: 'Tentar novamente' })).toBeVisible()
    expect(screen.queryByRole('heading', { name: 'Armadilha não encontrada' })).not.toBeInTheDocument()
  })

  it('oculta o gráfico sem medições e orienta a enviar a primeira imagem', async () => {
    mockDetalhe()
    renderDetalhe()

    expect(await screen.findByText('Nenhuma análise neste refil')).toBeVisible()
    expect(screen.queryByRole('img', { name: /Evolução da cobertura/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('group', { name: 'Escopo temporal' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Enviar a primeira imagem' })).toHaveAttribute(
      'href',
      '/analises/nova',
    )
  })

  it('exibe a imagem única e a miniatura para uma medição real', async () => {
    mockDetalhe([buildAnalise('a-1', '2026-10-16T08:00:00Z', 42.5)])
    renderDetalhe()

    expect(
      await screen.findByRole('img', { name: /Imagem da armadilha registrada em/ }),
    ).toBeVisible()
    expect(screen.queryByRole('heading', { name: /^Quadro / })).not.toBeInTheDocument()
    expect(screen.getAllByText('Cobertura: 42,50%')).not.toHaveLength(0)
    expect(screen.getAllByRole('img', { name: /Imagem original da análise/ })).toHaveLength(1)
    expect(screen.queryByRole('img', { name: /Evolução da cobertura/ })).not.toBeInTheDocument()
  })

  it('mostra a ação para iniciar um refil sem apresentar percentuais ausentes', async () => {
    vi.mocked(getArmadilha).mockResolvedValue(
      buildArmadilha({
        refil_ativo: null,
        percentual_atual: null,
        status: null,
        dias_ate_saturar: null,
        limiar_trocar: 20,
      }),
    )
    vi.mocked(listAnalises).mockResolvedValue([])
    renderDetalhe()

    expect(await screen.findByText(/Sem refil ativo/)).toBeVisible()
    expect(screen.getByRole('button', { name: 'Registrar refil' })).toBeVisible()
    expect(screen.queryByText('Cobertura atual')).not.toBeInTheDocument()
    expect(screen.queryByText(/\d+,\d{2}%/)).not.toBeInTheDocument()
  })

  it('preserva os dados atuais enquanto uma recarga após troca está pendente', async () => {
    mockDetalhe([buildAnalise('a-1', '2026-10-16T08:00:00Z', 42.5)])
    vi.mocked(getArmadilha).mockResolvedValueOnce(buildArmadilha()).mockImplementationOnce(
      () => new Promise(() => undefined),
    )
    vi.mocked(listAnalises).mockResolvedValueOnce([buildAnalise('a-1', '2026-10-16T08:00:00Z', 42.5)])
      .mockImplementationOnce(() => new Promise(() => undefined))
    vi.mocked(replaceRefil).mockResolvedValue({
      refil_encerrado: null,
      refil_novo: { id: 'refil-2', data_instalacao: '2026-10-16', dias_em_uso: 0 },
    })
    renderDetalhe()

    await screen.findByRole('heading', { name: 'ARM-001', level: 1 })
    fireEvent.click(screen.getByRole('button', { name: 'Registrar troca de refil' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar troca' }))

    await waitFor(() => expect(getArmadilha).toHaveBeenCalledTimes(2))
    expect(screen.getByRole('heading', { name: 'ARM-001', level: 1 })).toBeVisible()
    expect(screen.getAllByText('Cobertura: 42,50%')).not.toHaveLength(0)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
