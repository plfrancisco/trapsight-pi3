import { act, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import Timelapse from './Timelapse'
import { ApiError } from '../services/erros'
import type { Analise, RefilAnterior } from '../services/tipos'

vi.mock('../services/analises', () => ({ listAnalises: vi.fn() }))

import { listAnalises } from '../services/analises'

function buildAnalise(
  id: string,
  analisadoEm: string,
  percentual: number,
  refilId = 'refil-1',
): Analise {
  return {
    id,
    refil_id: refilId,
    armadilha_id: 'armadilha-1',
    analisado_em: analisadoEm,
    percentual_coberto: percentual,
    status: percentual >= 70 ? 'trocar' : percentual >= 40 ? 'atencao' : 'ok',
    modelo_versao: '1.0.0',
    imagem_url: `/analises/${id}/imagem`,
    mascara_url: `/analises/${id}/mascara`,
  }
}

const analisesAtivas = [
  buildAnalise('analise-1', '2026-10-01T08:00:00Z', 20),
  buildAnalise('analise-2', '2026-10-05T08:00:00Z', 45),
  buildAnalise('analise-3', '2026-10-10T08:00:00Z', 72),
]

const refisAnteriores: RefilAnterior[] = [
  {
    id: 'refil-ant-1',
    data_instalacao: '2026-08-01',
    data_troca: '2026-09-01',
    dias_ate_troca: 31,
  },
  {
    id: 'refil-ant-2',
    data_instalacao: '2026-09-01',
    data_troca: '2026-09-30',
    dias_ate_troca: 29,
  },
]

function renderTimelapse(analises: Analise[] = analisesAtivas) {
  return render(
    <Timelapse
      armadilhaId="armadilha-1"
      analisesAtivas={analises}
      refisAnteriores={refisAnteriores}
    />,
  )
}

describe('Timelapse', () => {
  beforeEach(() => {
    vi.mocked(listAnalises).mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('exibe somente a imagem quando há uma análise e oferece acesso ao histórico antigo', () => {
    renderTimelapse([analisesAtivas[0]])

    expect(screen.getByRole('img', { name: /Imagem da armadilha registrada/ })).toBeVisible()
    expect(screen.queryByRole('heading', { name: /Quadro/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Reproduzir' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Pausar' })).not.toBeInTheDocument()
    expect(screen.queryByRole('slider')).not.toBeInTheDocument()
    expect(screen.queryByRole('radio')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ver histórico completo' })).toBeVisible()
  })

  it('busca o histórico completo sob demanda uma vez e conserva o resultado ao alternar', async () => {
    const historico = [
      buildAnalise('historico-1', '2026-08-05T08:00:00Z', 35, 'refil-ant-1'),
      buildAnalise('historico-2', '2026-09-10T08:00:00Z', 65, 'refil-ant-2'),
      analisesAtivas[0],
    ]
    let concluirCarregamento: ((analises: Analise[]) => void) | undefined
    vi.mocked(listAnalises).mockImplementation(
      () => new Promise((resolve) => {
        concluirCarregamento = resolve
      }),
    )
    renderTimelapse([analisesAtivas[0]])

    expect(screen.queryByRole('button', { name: 'Reproduzir' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Ver histórico completo' }))
    expect(screen.getByRole('status')).toHaveTextContent('Carregando')
    await act(async () => {
      concluirCarregamento?.(historico)
      await Promise.resolve()
    })
    expect(screen.getByRole('heading', { name: 'Quadro 1 de 3' })).toBeVisible()
    expect(listAnalises).toHaveBeenCalledOnce()
    expect(listAnalises).toHaveBeenCalledWith('armadilha-1', {
      escopo: 'completo',
      limite: 1000,
    })

    fireEvent.click(screen.getByRole('radio', { name: 'Refil ativo' }))
    expect(
      screen.getByRole('img', { name: /Imagem da armadilha registrada em/ }),
    ).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Ver histórico completo' }))

    expect(screen.getByRole('heading', { name: 'Quadro 1 de 3' })).toBeVisible()
    expect(listAnalises).toHaveBeenCalledOnce()
  })

  it('mostra erro do histórico e permite tentar novamente', async () => {
    const usuario = userEvent.setup()
    vi.mocked(listAnalises)
      .mockRejectedValueOnce(new ApiError('FALHA_DE_REDE', 'Falha temporária.', 503))
      .mockResolvedValueOnce([analisesAtivas[0], analisesAtivas[1]])
    renderTimelapse([analisesAtivas[0]])

    await usuario.click(screen.getByRole('button', { name: 'Ver histórico completo' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Falha temporária.')
    await usuario.click(screen.getByRole('button', { name: 'Tentar novamente' }))

    expect(await screen.findByRole('heading', { name: 'Quadro 1 de 2' })).toBeVisible()
    expect(listAnalises).toHaveBeenCalledTimes(2)
  })

  it('pausa e volta ao primeiro quadro ao trocar de escopo', async () => {
    vi.useFakeTimers()
    vi.mocked(listAnalises).mockResolvedValue(analisesAtivas)
    renderTimelapse()

    fireEvent.click(screen.getByRole('button', { name: 'Reproduzir' }))
    await act(async () => {
      vi.advanceTimersByTime(500)
    })
    expect(screen.getByRole('heading', { name: 'Quadro 2 de 3' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Pausar' })).toBeVisible()

    fireEvent.click(screen.getByRole('radio', { name: 'Histórico completo' }))
    await act(async () => {
      await Promise.resolve()
    })
    expect(screen.getByRole('heading', { name: 'Quadro 1 de 3' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Reproduzir' })).toBeVisible()
    expect(listAnalises).toHaveBeenCalledOnce()
  })

  it('pausa a reprodução quando o controle deslizante seleciona outro quadro', async () => {
    vi.useFakeTimers()
    renderTimelapse()
    fireEvent.click(screen.getByRole('button', { name: 'Reproduzir' }))

    await act(async () => {
      vi.advanceTimersByTime(500)
    })
    expect(screen.getByRole('heading', { name: 'Quadro 2 de 3' })).toBeVisible()

    fireEvent.change(screen.getByRole('slider', { name: 'Quadro atual: 2 de 3' }), {
      target: { value: '2' },
    })
    expect(screen.getByRole('heading', { name: 'Quadro 3 de 3' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Reproduzir' })).toBeVisible()

    await act(async () => {
      vi.advanceTimersByTime(1000)
    })
    expect(screen.getByRole('heading', { name: 'Quadro 3 de 3' })).toBeVisible()
  })

  it('não renderiza gráfico ou timelapse sem análises ativas', () => {
    const { container } = render(
      <Timelapse armadilhaId="armadilha-1" analisesAtivas={[]} refisAnteriores={[]} />,
    )

    expect(container).toBeEmptyDOMElement()
  })
})
