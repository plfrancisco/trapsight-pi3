import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useParams } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import CadastroArmadilhaPage from './CadastroArmadilhaPage'
import { localDateIso } from '../lib/datas'
import { ApiError } from '../services/erros'
import type { ArmadilhaDetalhe } from '../services/tipos'

vi.mock('../services/armadilhas', () => ({
  createArmadilha: vi.fn(),
  getArmadilha: vi.fn(),
  updateArmadilha: vi.fn(),
}))

import { createArmadilha, getArmadilha, updateArmadilha } from '../services/armadilhas'

const armadilha: ArmadilhaDetalhe = {
  id: 'arm-1',
  identificador: 'ARM-001',
  modelo: 'StickFly K-45',
  localizacao: 'Depósito',
  data_instalacao: '2026-10-01',
  refil_ativo: null,
  refis_anteriores: [],
  percentual_atual: null,
  status: null,
  dias_ate_saturar: null,
}

function DestinoArmadilha() {
  const { id } = useParams()
  return <p>Detalhe da armadilha {id}</p>
}

function renderCadastro(caminho: string) {
  return render(
    <MemoryRouter initialEntries={[caminho]}>
      <Routes>
        <Route element={<CadastroArmadilhaPage />} path="/armadilhas/nova" />
        <Route element={<CadastroArmadilhaPage />} path="/armadilhas/:id/editar" />
        <Route element={<DestinoArmadilha />} path="/armadilhas/:id" />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.mocked(createArmadilha).mockReset()
  vi.mocked(getArmadilha).mockReset()
  vi.mocked(updateArmadilha).mockReset()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('CadastroArmadilhaPage', () => {
  it('envia identificador aparado, campos vazios como null e a opção inicial de refil', async () => {
    const usuario = userEvent.setup()
    vi.mocked(createArmadilha).mockResolvedValue({ ...armadilha, id: 'arm-nova' })
    renderCadastro('/armadilhas/nova')

    await usuario.type(screen.getByLabelText('Identificador *'), '  ARM-007  ')
    const dataInstalacao = localDateIso(new Date())
    expect(screen.getByLabelText('Data de instalação')).toHaveValue(dataInstalacao)
    expect(screen.getByRole('checkbox', { name: 'Criar o primeiro refil agora' })).toBeChecked()
    await usuario.click(screen.getByRole('button', { name: 'Cadastrar armadilha' }))

    await screen.findByText('Detalhe da armadilha arm-nova')
    expect(createArmadilha).toHaveBeenCalledWith({
      identificador: 'ARM-007',
      modelo: null,
      localizacao: null,
      data_instalacao: dataInstalacao,
      criar_refil_inicial: true,
    })
  })

  it('valida um identificador que fica vazio depois de aparar espaços', async () => {
    const usuario = userEvent.setup()
    renderCadastro('/armadilhas/nova')

    await usuario.type(screen.getByLabelText('Identificador *'), '   ')
    await usuario.click(screen.getByRole('button', { name: 'Cadastrar armadilha' }))

    expect(await screen.findByText('Informe o identificador da armadilha.')).toBeVisible()
    expect(createArmadilha).not.toHaveBeenCalled()
  })

  it('associa erro e foco ao identificador enviado vazio', async () => {
    const usuario = userEvent.setup()
    renderCadastro('/armadilhas/nova')

    await usuario.click(screen.getByRole('button', { name: 'Cadastrar armadilha' }))

    const campo = screen.getByLabelText('Identificador *')
    expect(await screen.findByText('Informe o identificador da armadilha.')).toBeVisible()
    expect(campo).toHaveFocus()
    expect(campo).toHaveAttribute('aria-invalid', 'true')
    expect(campo).toHaveAttribute('aria-describedby', 'identificador-ajuda identificador-erro')
    expect(createArmadilha).not.toHaveBeenCalled()
  })

  it('mantém validação quando a data do primeiro refil fica vazia', async () => {
    const usuario = userEvent.setup()
    renderCadastro('/armadilhas/nova')

    await usuario.type(screen.getByLabelText('Identificador *'), 'ARM-SEM-DATA')
    await usuario.clear(screen.getByLabelText('Data de instalação'))
    await usuario.click(screen.getByRole('button', { name: 'Cadastrar armadilha' }))

    expect(
      await screen.findByText(
        'Informe a data de instalação para iniciar o primeiro refil.',
      ),
    ).toBeVisible()
    expect(createArmadilha).not.toHaveBeenCalled()
  })

  it('mostra erro de identificador duplicado junto ao campo pelo código da API', async () => {
    const usuario = userEvent.setup()
    vi.mocked(createArmadilha).mockRejectedValue(
      new ApiError('IDENTIFICADOR_DUPLICADO', 'texto não usado na interface', 409),
    )
    renderCadastro('/armadilhas/nova')

    await usuario.type(screen.getByLabelText('Identificador *'), 'ARM-001')
    await usuario.click(screen.getByRole('button', { name: 'Cadastrar armadilha' }))

    const campo = screen.getByLabelText('Identificador *')
    expect(
      await screen.findByText(
        'Já existe uma armadilha com este identificador. Escolha outro.',
      ),
    ).toBeVisible()
    expect(campo).toHaveAttribute('aria-invalid', 'true')
    expect(campo).toHaveAttribute('aria-describedby', 'identificador-ajuda identificador-erro')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('carrega a armadilha para edição e envia apenas os três campos permitidos', async () => {
    const usuario = userEvent.setup()
    vi.mocked(getArmadilha).mockResolvedValue(armadilha)
    vi.mocked(updateArmadilha).mockResolvedValue({ ...armadilha, localizacao: 'Recebimento' })
    renderCadastro('/armadilhas/arm-1/editar')

    const campoIdentificador = await screen.findByLabelText('Identificador *')
    expect(campoIdentificador).toHaveValue('ARM-001')
    expect(screen.getByLabelText('Data de instalação')).toHaveValue('2026-10-01')
    expect(screen.getByLabelText('Data de instalação')).toHaveAttribute('readonly')
    await usuario.clear(screen.getByLabelText('Localização'))
    await usuario.type(screen.getByLabelText('Localização'), 'Recebimento')
    await usuario.click(screen.getByRole('button', { name: 'Salvar alterações' }))

    await screen.findByText('Detalhe da armadilha arm-1')
    await waitFor(() =>
      expect(updateArmadilha).toHaveBeenCalledWith('arm-1', {
        identificador: 'ARM-001',
        modelo: 'StickFly K-45',
        localizacao: 'Recebimento',
      }),
    )
    expect(vi.mocked(updateArmadilha).mock.calls[0][1]).not.toHaveProperty(
      'data_instalacao',
    )
  })

  it('preenche a data de instalação com o dia local, mesmo perto da meia-noite', () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(2026, 9, 16, 23, 30))

    renderCadastro('/armadilhas/nova')

    expect(screen.getByLabelText('Data de instalação')).toHaveValue('2026-10-16')
  })

  it('não preenche a data atual na edição quando não há data registrada', async () => {
    vi.mocked(getArmadilha).mockResolvedValue({
      ...armadilha,
      data_instalacao: null,
    })
    renderCadastro('/armadilhas/arm-1/editar')

    expect(await screen.findByLabelText('Data de instalação')).toHaveValue('')
  })

  it('mostra um estado de não encontrada com retorno ao dashboard', async () => {
    vi.mocked(getArmadilha).mockRejectedValue(
      new ApiError('ARMADILHA_NAO_ENCONTRADA', 'mensagem do serviço', 404),
    )
    renderCadastro('/armadilhas/ausente/editar')

    expect(await screen.findByText('Armadilha não encontrada')).toBeVisible()
    expect(screen.getByRole('link', { name: 'Ir para o dashboard' })).toHaveAttribute(
      'href',
      '/',
    )
  })
})
