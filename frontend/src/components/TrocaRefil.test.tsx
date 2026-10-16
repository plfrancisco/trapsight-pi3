import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import TrocaRefil from './TrocaRefil'
import { ApiError } from '../services/erros'

vi.mock('../services/armadilhas', () => ({ replaceRefil: vi.fn() }))

import { replaceRefil } from '../services/armadilhas'

describe('TrocaRefil', () => {
  beforeEach(() => {
    vi.mocked(replaceRefil).mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('abre um diálogo nativo e não registra a troca antes da confirmação', async () => {
    const usuario = userEvent.setup()
    vi.mocked(replaceRefil).mockResolvedValue({ refil_encerrado: null, refil_novo: {
      id: 'refil-2', data_instalacao: '2026-10-16', dias_em_uso: 0,
    } })
    render(<TrocaRefil onConcluir={vi.fn()} armadilhaId="arm-1" temRefilAtivo />)

    await usuario.click(screen.getByRole('button', { name: 'Registrar troca de refil' }))

    const dialogo = screen.getByRole('dialog', { name: 'Confirmar troca de refil' })
    expect(dialogo).toHaveAttribute('open')
    expect(dialogo).toHaveAttribute('aria-describedby', 'descricao-confirmacao-troca')
    expect(dialogo).toHaveTextContent(
      'Encerrar o refil atual e iniciar um novo hoje? A série de medições recomeça do zero.',
    )
    expect(screen.getByRole('button', { name: 'Confirmar troca' })).toHaveFocus()
    expect(replaceRefil).not.toHaveBeenCalled()
  })

  it('usa a data civil local e recarrega após o sucesso', async () => {
    const usuario = userEvent.setup()
    const onConcluir = vi.fn()
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(2026, 9, 16, 23, 30))
    vi.mocked(replaceRefil).mockResolvedValue({ refil_encerrado: null, refil_novo: {
      id: 'refil-2', data_instalacao: '2026-10-16', dias_em_uso: 0,
    } })
    render(<TrocaRefil onConcluir={onConcluir} armadilhaId="arm-1" temRefilAtivo />)

    await usuario.click(screen.getByRole('button', { name: 'Registrar troca de refil' }))
    await usuario.click(screen.getByRole('button', { name: 'Confirmar troca' }))

    await waitFor(() => expect(replaceRefil).toHaveBeenCalledWith('arm-1', {
      data_instalacao: '2026-10-16',
    }))
    expect(onConcluir).toHaveBeenCalledOnce()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('mantém o diálogo aberto com a mensagem da API em caso de falha', async () => {
    const usuario = userEvent.setup()
    const onConcluir = vi.fn()
    vi.mocked(replaceRefil).mockRejectedValue(
      new ApiError('REFIL_INVALIDO', 'Não foi possível concluir a troca.', 409),
    )
    render(<TrocaRefil onConcluir={onConcluir} armadilhaId="arm-1" temRefilAtivo />)

    await usuario.click(screen.getByRole('button', { name: 'Registrar troca de refil' }))
    await userEvent.click(screen.getByRole('button', { name: 'Confirmar troca' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Não foi possível concluir a troca.',
    )
    expect(screen.getByRole('dialog')).toHaveAttribute('open')
    expect(onConcluir).not.toHaveBeenCalled()
  })

  it('fecha com Cancelar, não chama a API e devolve o foco ao acionador', async () => {
    const usuario = userEvent.setup()
    render(<TrocaRefil onConcluir={vi.fn()} armadilhaId="arm-1" temRefilAtivo />)
    const acionador = screen.getByRole('button', { name: 'Registrar troca de refil' })

    await usuario.click(acionador)
    await usuario.click(within(screen.getByRole('dialog')).getByRole('button', {
      name: 'Cancelar',
    }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(acionador).toHaveFocus()
    expect(replaceRefil).not.toHaveBeenCalled()
  })

  it('fecha no evento nativo de Escape e mantém o rótulo sem refil ativo', async () => {
    const usuario = userEvent.setup()
    render(<TrocaRefil onConcluir={vi.fn()} armadilhaId="arm-1" temRefilAtivo={false} />)
    const acionador = screen.getByRole('button', { name: 'Registrar refil' })

    await usuario.click(acionador)
    const dialogo = screen.getByRole('dialog')
    const eventoEscape = new Event('cancel', { cancelable: true })
    fireEvent(dialogo, eventoEscape)

    expect(eventoEscape.defaultPrevented).toBe(true)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(acionador).toHaveFocus()
    expect(screen.queryByRole('button', { name: 'Registrar troca de refil' })).not.toBeInTheDocument()
    expect(replaceRefil).not.toHaveBeenCalled()
  })

  it('não fecha ao clicar no fundo do diálogo', async () => {
    const usuario = userEvent.setup()
    render(<TrocaRefil onConcluir={vi.fn()} armadilhaId="arm-1" temRefilAtivo />)

    await usuario.click(screen.getByRole('button', { name: 'Registrar troca de refil' }))
    const dialogo = screen.getByRole('dialog')
    fireEvent.click(dialogo)

    expect(dialogo).toHaveAttribute('open')
    expect(replaceRefil).not.toHaveBeenCalled()
  })

  it('desabilita Confirmar e Cancelar e impede Escape durante a chamada', async () => {
    const usuario = userEvent.setup()
    let concluirRequisicao: (() => void) | undefined
    vi.mocked(replaceRefil).mockImplementation(
      () => new Promise((resolve) => {
        concluirRequisicao = () => resolve({
          refil_encerrado: null,
          refil_novo: { id: 'refil-2', data_instalacao: '2026-10-16', dias_em_uso: 0 },
        })
      }),
    )
    render(<TrocaRefil onConcluir={vi.fn()} armadilhaId="arm-1" temRefilAtivo />)

    await usuario.click(screen.getByRole('button', { name: 'Registrar troca de refil' }))
    await usuario.click(screen.getByRole('button', { name: 'Confirmar troca' }))

    const dialogo = screen.getByRole('dialog')
    expect(screen.getByRole('button', { name: 'Registrando…' })).toBeDisabled()
    expect(within(dialogo).getByRole('button', { name: 'Cancelar' })).toBeDisabled()
    const eventoEscape = new Event('cancel', { cancelable: true })
    fireEvent(dialogo, eventoEscape)
    expect(eventoEscape.defaultPrevented).toBe(true)
    expect(dialogo).toHaveAttribute('open')

    await act(async () => {
      concluirRequisicao?.()
    })
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })
})
