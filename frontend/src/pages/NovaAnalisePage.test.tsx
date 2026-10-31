import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import NovaAnalisePage from './NovaAnalisePage'
import { ApiError } from '../services/erros'
import type { Analise, ArmadilhaLista } from '../services/tipos'

vi.mock('../services/armadilhas', () => ({ listArmadilhas: vi.fn() }))
vi.mock('../services/analises', () => ({ createAnalise: vi.fn() }))

import { createAnalise } from '../services/analises'
import { listArmadilhas } from '../services/armadilhas'

const armadilhaComRefil: ArmadilhaLista = {
  id: 'arm-1',
  identificador: 'ARM-001',
  localizacao: 'Depósito',
  modelo: 'StickFly K-45',
  modelo_id: null,
  refil_ativo: { id: 'refil-1', data_instalacao: '2026-10-01', dias_em_uso: 13 },
  percentual_atual: null,
  status: null,
  dias_ate_saturar: null,
  limiar_trocar: 20,
  ultima_analise_em: null,
  em_alerta_desde: null,
}

const armadilhaSemRefil: ArmadilhaLista = {
  ...armadilhaComRefil,
  id: 'arm-sem-refil',
  identificador: 'ARM-SEM-REFIL',
  refil_ativo: null,
}

const analise: Analise = {
  id: 'analise-1',
  refil_id: 'refil-1',
  armadilha_id: 'arm-1',
  analisado_em: '2026-10-14T12:00:00Z',
  percentual_coberto: 64.3,
  status: 'atencao',
  modelo_versao: 'v1.2.0+a3f9c2e1',
  imagem_url: '/api/analises/analise-1/imagem',
}

const renderPage = () =>
  render(
    <MemoryRouter>
      <NovaAnalisePage />
    </MemoryRouter>,
  )

async function selectValidImage(usuario: ReturnType<typeof userEvent.setup>) {
  await usuario.upload(
    screen.getByLabelText('Imagem da armadilha'),
    new File(['imagem'], 'placa.jpg', { type: 'image/jpeg' }),
  )
}

async function selectArmadilha(usuario: ReturnType<typeof userEvent.setup>) {
  await usuario.selectOptions(await screen.findByRole('combobox'), 'arm-1')
}

beforeEach(() => {
  vi.mocked(listArmadilhas).mockReset().mockResolvedValue([armadilhaComRefil])
  vi.mocked(createAnalise).mockReset()
})

describe('NovaAnalisePage', () => {
  it('bloqueia o envio de armadilha sem refil e oferece o link para registrá-lo', async () => {
    const usuario = userEvent.setup()
    vi.mocked(listArmadilhas).mockResolvedValue([armadilhaSemRefil])
    renderPage()

    await usuario.selectOptions(await screen.findByRole('combobox'), 'arm-sem-refil')
    await selectValidImage(usuario)

    expect(
      screen.getByText(/Esta armadilha está sem refil ativo/),
    ).toBeVisible()
    expect(screen.getByRole('link', { name: 'Abrir armadilha' })).toHaveAttribute(
      'href',
      '/armadilhas/arm-sem-refil',
    )
    expect(screen.getByRole('button', { name: 'Enviar para análise' })).toBeDisabled()
    expect(createAnalise).not.toHaveBeenCalled()
  })

  it('mostra erro antes do envio quando tipo e extensão do arquivo não correspondem', async () => {
    const usuario = userEvent.setup({ applyAccept: false })
    renderPage()
    await selectArmadilha(usuario)
    await usuario.upload(
      screen.getByLabelText('Imagem da armadilha'),
      new File(['imagem'], 'placa.png', { type: 'image/jpeg' }),
    )

    expect(
      await screen.findByText('Selecione um arquivo JPEG (.jpg ou .jpeg) ou PNG (.png).'),
    ).toBeVisible()
    expect(screen.getByRole('button', { name: 'Enviar para análise' })).toBeDisabled()
    expect(createAnalise).not.toHaveBeenCalled()
  })

  it('exibe o resultado e permite começar outra análise limpando a seleção', async () => {
    const usuario = userEvent.setup()
    vi.mocked(createAnalise).mockResolvedValue(analise)
    renderPage()
    await selectArmadilha(usuario)
    await selectValidImage(usuario)
    await usuario.click(screen.getByRole('button', { name: 'Enviar para análise' }))

    expect(await screen.findByRole('heading', { name: 'Resultado da análise' })).toBeVisible()
    expect(screen.getByText('64,30%')).toBeVisible()
    expect(screen.getByText('v1.2.0+a3f9c2e1')).toBeVisible()
    const chamada = vi.mocked(createAnalise).mock.calls[0]
    expect(chamada?.[0]).toBe('arm-1')
    expect(chamada?.[1]).toBeInstanceOf(File)
    expect(chamada?.[2]).toBeInstanceOf(AbortSignal)

    await usuario.click(screen.getByRole('button', { name: 'Nova análise' }))
    expect(screen.queryByRole('heading', { name: 'Resultado da análise' })).not.toBeInTheDocument()
    expect(screen.getByRole('combobox')).toHaveValue('')
    expect(screen.getByLabelText('Imagem da armadilha')).toHaveValue('')
  })

  it('permite cancelar o upload sem mostrar erro', async () => {
    const usuario = userEvent.setup()
    vi.mocked(createAnalise).mockImplementation(
      (_armadilhaId, _arquivo, signal) =>
        new Promise<Analise>((_resolve, reject) => {
          signal?.addEventListener(
            'abort',
            () => reject(new DOMException('Cancelada', 'AbortError')),
            { once: true },
          )
        }),
    )
    renderPage()
    await selectArmadilha(usuario)
    await selectValidImage(usuario)
    await usuario.click(screen.getByRole('button', { name: 'Enviar para análise' }))

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Enviando e analisando a imagem',
    )
    await usuario.click(screen.getByRole('button', { name: 'Cancelar envio' }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Enviar para análise' })).toBeEnabled(),
    )
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Resultado da análise' })).not.toBeInTheDocument()
  })

  it('mostra mensagem própria para falha de inferência e não mantém resultado parcial', async () => {
    const usuario = userEvent.setup()
    vi.mocked(createAnalise).mockRejectedValue(
      new ApiError('FALHA_INFERENCIA', 'mensagem técnica original', 500),
    )
    renderPage()
    await selectArmadilha(usuario)
    await selectValidImage(usuario)
    await usuario.click(screen.getByRole('button', { name: 'Enviar para análise' }))

    expect(
      await screen.findByRole('alert'),
    ).toHaveTextContent('A análise não pôde ser concluída. Tente novamente mais tarde.')
    expect(screen.queryByRole('heading', { name: 'Resultado da análise' })).not.toBeInTheDocument()
  })
})
