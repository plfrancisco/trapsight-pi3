import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useParams } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import CadastroArmadilhaPage from './CadastroArmadilhaPage'
import { localDateIso } from '../lib/datas'
import { ApiError } from '../services/erros'
import type { ArmadilhaDetalhe, ModeloArmadilha } from '../services/tipos'

vi.mock('../services/modelos', () => ({ listModelos: vi.fn() }))

vi.mock('../services/armadilhas', () => ({
  createArmadilha: vi.fn(),
  getArmadilha: vi.fn(),
  updateArmadilha: vi.fn(),
  sendFotoArmadilha: vi.fn(),
  deleteFotoArmadilha: vi.fn(),
}))

import {
  createArmadilha,
  deleteFotoArmadilha,
  getArmadilha,
  sendFotoArmadilha,
  updateArmadilha,
} from '../services/armadilhas'
import { listModelos } from '../services/modelos'

const armadilha: ArmadilhaDetalhe = {
  id: 'arm-1',
  identificador: 'ARM-001',
  modelo: 'StickFly K-45',
  modelo_id: 'mod-1',
  localizacao: 'Depósito',
  data_instalacao: '2026-10-01',
  refil_ativo: null,
  refis_anteriores: [],
  percentual_atual: null,
  status: null,
  dias_ate_saturar: null,
  limiar_trocar: 20,
  foto_tipo: 'padrao',
  foto_url: null,
}

const stickfly: ModeloArmadilha = {
  id: 'mod-1',
  codigo: 'stickfly-k45',
  nome: 'StickFly K-45',
  fabricante: 'StickFly',
  descricao: 'Armadilha de parede com lâmpadas UVA.',
  atracao: 'UV-A',
  refil_largura_mm: 450,
  refil_altura_mm: 220,
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
  vi.mocked(sendFotoArmadilha).mockReset()
  vi.mocked(deleteFotoArmadilha).mockReset()
  vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:previa'), revokeObjectURL: vi.fn() }))
  vi.mocked(listModelos).mockReset()
  vi.mocked(listModelos).mockResolvedValue([stickfly])
})

afterEach(() => {
  vi.useRealTimers()
})

describe('CadastroArmadilhaPage', () => {
  it('envia identificador aparado, campos vazios como null e a opção inicial de refil', async () => {
    const usuario = userEvent.setup()
    vi.mocked(createArmadilha).mockResolvedValue({ ...armadilha, id: 'arm-nova' })
    renderCadastro('/armadilhas/nova')
    await screen.findByText('StickFly K-45', { selector: '.model-picker__selected-name' })

    await usuario.type(screen.getByLabelText('Identificador *'), '  ARM-007  ')
    const dataInstalacao = localDateIso(new Date())
    expect(screen.getByLabelText('Data de instalação')).toHaveValue(dataInstalacao)
    expect(screen.getByRole('checkbox', { name: 'Criar o primeiro refil agora' })).toBeChecked()
    await usuario.click(screen.getByRole('button', { name: 'Cadastrar armadilha' }))

    await screen.findByText('Detalhe da armadilha arm-nova')
    expect(createArmadilha).toHaveBeenCalledWith({
      identificador: 'ARM-007',
      modelo_id: 'mod-1',
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
        modelo_id: 'mod-1',
        localizacao: 'Recebimento',
      }),
    )
    expect(vi.mocked(updateArmadilha).mock.calls[0][1]).not.toHaveProperty(
      'data_instalacao',
    )
  })

  it('lista os modelos do fabricante e exige a escolha quando há mais de um', async () => {
    const usuario = userEvent.setup()
    const outro: ModeloArmadilha = { ...stickfly, id: 'mod-2', codigo: 'k-60', nome: 'StickFly K-60' }
    vi.mocked(listModelos).mockResolvedValue([stickfly, outro])
    vi.mocked(createArmadilha).mockResolvedValue({ ...armadilha, id: 'arm-nova' })
    renderCadastro('/armadilhas/nova')

    await screen.findByText('Selecione um modelo')
    await usuario.click(screen.getByText('Selecione um modelo'))
    const opcao = await screen.findByRole('button', { name: 'StickFly K-60' })
    expect(screen.getByRole('button', { name: 'StickFly K-45' })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
    await usuario.type(screen.getByLabelText('Identificador *'), 'ARM-010')
    await usuario.click(screen.getByRole('button', { name: 'Cadastrar armadilha' }))

    expect(await screen.findByText('Escolha o modelo da armadilha.')).toBeVisible()
    expect(createArmadilha).not.toHaveBeenCalled()

    await usuario.click(opcao)
    await usuario.click(screen.getByRole('button', { name: 'Cadastrar armadilha' }))

    await screen.findByText('Detalhe da armadilha arm-nova')
    expect(createArmadilha).toHaveBeenCalledWith(
      expect.objectContaining({ identificador: 'ARM-010', modelo_id: 'mod-2' }),
    )
  })

  it('marca o modelo cadastrado ao editar uma armadilha', async () => {
    vi.mocked(getArmadilha).mockResolvedValue(armadilha)
    renderCadastro('/armadilhas/arm-1/editar')

    expect(
      await screen.findByText('StickFly K-45', { selector: '.model-picker__selected-name' }),
    ).toBeVisible()
  })

  it('informa a falha ao carregar os modelos e permite tentar de novo', async () => {
    const usuario = userEvent.setup()
    vi.mocked(listModelos).mockRejectedValueOnce(new Error('rede'))
    renderCadastro('/armadilhas/nova')

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Não foi possível carregar os modelos de armadilha.',
    )
    expect(screen.getByRole('button', { name: 'Cadastrar armadilha' })).toBeDisabled()

    await usuario.click(screen.getByRole('button', { name: 'Tentar novamente' }))

    expect(
      await screen.findByText('StickFly K-45', { selector: '.model-picker__selected-name' }),
    ).toBeVisible()
  })

  it('preenche a data de instalação com o dia local, mesmo perto da meia-noite', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(2026, 9, 16, 23, 30))

    renderCadastro('/armadilhas/nova')

    expect(await screen.findByLabelText('Data de instalação')).toHaveValue('2026-10-16')
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

  it('trata UUID inválida como armadilha ausente no modo de edição', async () => {
    vi.mocked(getArmadilha).mockRejectedValue(
      new ApiError('VALIDACAO_FALHOU', 'UUID inválida.', 422, {
        campos_invalidos: [{ campo: 'armadilha_id', tipo: 'uuid_parsing' }],
      }),
    )
    renderCadastro('/armadilhas/id-invalido/editar')

    expect(await screen.findByText('Armadilha não encontrada')).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Tentar novamente' })).not.toBeInTheDocument()
  })

  it('começa na foto padrão e só pede o arquivo quando a foto real é escolhida', async () => {
    const usuario = userEvent.setup()
    renderCadastro('/armadilhas/nova')

    expect(screen.getByRole('radio', { name: 'Foto padrão do modelo' })).toBeChecked()
    expect(screen.queryByLabelText('Arquivo da foto')).not.toBeInTheDocument()

    await usuario.click(screen.getByRole('radio', { name: 'Foto real da armadilha' }))

    expect(screen.getByLabelText('Arquivo da foto')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Voltar à foto padrão' })).toBeVisible()
  })

  it('recusa na tela um arquivo que não é JPEG nem PNG e um arquivo acima de 4 MB', async () => {
    const usuario = userEvent.setup({ applyAccept: false })
    renderCadastro('/armadilhas/nova')
    await usuario.click(screen.getByRole('radio', { name: 'Foto real da armadilha' }))
    const campo = screen.getByLabelText('Arquivo da foto')

    await usuario.upload(campo, new File(['x'], 'nota.txt', { type: 'text/plain' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/JPEG/)

    const grande = new File([new Uint8Array(4 * 1024 * 1024 + 1)], 'grande.jpg', { type: 'image/jpeg' })
    await usuario.upload(campo, grande)
    expect(await screen.findByRole('alert')).toHaveTextContent(/4 MB/)
    expect(sendFotoArmadilha).not.toHaveBeenCalled()
  })

  it('exige um arquivo quando a foto real é escolhida sem arquivo', async () => {
    const usuario = userEvent.setup()
    renderCadastro('/armadilhas/nova')
    await screen.findByText('StickFly K-45', { selector: '.model-picker__selected-name' })
    await usuario.type(screen.getByLabelText('Identificador *'), 'ARM-FOTO')
    await usuario.click(screen.getByRole('radio', { name: 'Foto real da armadilha' }))
    await usuario.click(screen.getByRole('button', { name: 'Cadastrar armadilha' }))

    expect(await screen.findByText(/Escolha a imagem da foto real/)).toBeVisible()
    expect(createArmadilha).not.toHaveBeenCalled()
  })

  it('cadastra a armadilha e envia a foto real escolhida', async () => {
    const usuario = userEvent.setup()
    vi.mocked(createArmadilha).mockResolvedValue({ ...armadilha, id: 'arm-nova' })
    vi.mocked(sendFotoArmadilha).mockResolvedValue({ foto_tipo: 'real', foto_url: '/api/x' })
    renderCadastro('/armadilhas/nova')
    await screen.findByText('StickFly K-45', { selector: '.model-picker__selected-name' })
    await usuario.type(screen.getByLabelText('Identificador *'), 'ARM-FOTO')
    await usuario.click(screen.getByRole('radio', { name: 'Foto real da armadilha' }))
    const foto = new File(['x'], 'foto.jpg', { type: 'image/jpeg' })
    await usuario.upload(screen.getByLabelText('Arquivo da foto'), foto)
    await usuario.click(screen.getByRole('button', { name: 'Cadastrar armadilha' }))

    await screen.findByText('Detalhe da armadilha arm-nova')
    expect(sendFotoArmadilha).toHaveBeenCalledWith('arm-nova', foto)
  })

  it('volta à foto padrão na edição e remove a foto real no servidor', async () => {
    const usuario = userEvent.setup()
    vi.mocked(getArmadilha).mockResolvedValue({
      ...armadilha,
      foto_tipo: 'real',
      foto_url: '/api/armadilhas/arm-1/foto?v=1',
    })
    vi.mocked(updateArmadilha).mockResolvedValue(armadilha)
    vi.mocked(deleteFotoArmadilha).mockResolvedValue(undefined)
    renderCadastro('/armadilhas/arm-1/editar')
    await screen.findByDisplayValue('ARM-001')

    expect(screen.getByRole('radio', { name: 'Foto real da armadilha' })).toBeChecked()
    await usuario.click(screen.getByRole('button', { name: 'Voltar à foto padrão' }))
    await usuario.click(screen.getByRole('button', { name: 'Salvar alterações' }))

    await screen.findByText('Detalhe da armadilha arm-1')
    expect(deleteFotoArmadilha).toHaveBeenCalledWith('arm-1')
    expect(sendFotoArmadilha).not.toHaveBeenCalled()
  })
})
