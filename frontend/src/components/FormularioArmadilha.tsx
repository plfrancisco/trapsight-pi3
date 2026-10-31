import { useCallback, useRef, useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router'
import { useCarregamento } from '../hooks/useCarregamento'
import { localDateIso } from '../lib/datas'
import { ApiError } from '../services/erros'
import {
  createArmadilha,
  deleteFotoArmadilha,
  sendFotoArmadilha,
  updateArmadilha,
} from '../services/armadilhas'
import { listModelos } from '../services/modelos'
import type { ArmadilhaDetalhe } from '../services/tipos'
import Botao from './Botao'
import CampoFormulario from './CampoFormulario'
import CampoFotoArmadilha, { type ModoFoto } from './CampoFotoArmadilha'
import EstadoCarregando from './EstadoCarregando'
import LinkBotao from './LinkBotao'
import MensagemErro from './MensagemErro'
import SeletorModelo from './SeletorModelo'

interface FormularioArmadilhaProps {
  id?: string
  dados: ArmadilhaDetalhe | null
}

function parseOptionalValue(valor: FormDataEntryValue | null): string | null {
  if (typeof valor !== 'string') return null
  return valor.trim() || null
}

/** Cadastra ou atualiza os dados editáveis de uma armadilha.
 * @param props Identificador da rota e dados carregados para edição.
 * @returns O formulário de cadastro ou edição.
 */
export default function FormularioArmadilha({
  id,
  dados,
}: FormularioArmadilhaProps) {
  const navigate = useNavigate()
  const avisoFoto = (useLocation().state as { avisoFoto?: string } | null)?.avisoFoto ?? null
  const [fotoModo, setFotoModo] = useState<ModoFoto>(dados?.foto_tipo ?? 'padrao')
  const [fotoArquivo, setFotoArquivo] = useState<File | null>(null)
  const [erroFoto, setErroFoto] = useState<string | null>(null)
  const identificadorRef = useRef<HTMLInputElement>(null)
  const dataInstalacaoRef = useRef<HTMLInputElement>(null)
  const [erroIdentificador, setErroIdentificador] = useState<string | null>(null)
  const [erroDataInstalacao, setErroDataInstalacao] = useState<string | null>(null)
  const [erroModelo, setErroModelo] = useState<string | null>(null)
  const carregarModelos = useCallback(
    (signal: AbortSignal) => listModelos(signal),
    [],
  )
  const {
    dados: modelos,
    erro: erroModelos,
    carregando: carregandoModelos,
    recarregar: recarregarModelos,
  } = useCarregamento(carregarModelos)
  const [erroEnvio, setErroEnvio] = useState<ApiError | string | null>(null)
  const [enviando, setEnviando] = useState(false)

  /** Grava a escolha de foto depois que a armadilha existe: envia a real ou volta à padrão. */
  const aplicarFoto = async (armadilhaId: string) => {
    if (fotoModo === 'real' && fotoArquivo !== null) {
      await sendFotoArmadilha(armadilhaId, fotoArquivo)
    } else if (fotoModo === 'padrao' && dados?.foto_tipo === 'real') {
      await deleteFotoArmadilha(armadilhaId)
    }
  }

  const saveArmadilha = async (evento: FormEvent<HTMLFormElement>) => {
    evento.preventDefault()
    setErroIdentificador(null)
    setErroDataInstalacao(null)
    setErroModelo(null)
    setErroEnvio(null)
    setErroFoto(null)

    const formulario = new FormData(evento.currentTarget)
    const identificador = String(formulario.get('identificador') ?? '').trim()
    if (!identificador) {
      setErroIdentificador('Informe o identificador da armadilha.')
      identificadorRef.current?.focus()
      return
    }

    const modeloId = parseOptionalValue(formulario.get('modelo_id'))
    if (!id && modeloId === null) {
      setErroModelo('Escolha o modelo da armadilha.')
      return
    }

    const criarRefilInicial = formulario.has('criar_refil_inicial')
    const dataInstalacao = parseOptionalValue(formulario.get('data_instalacao'))
    if (!id && criarRefilInicial && dataInstalacao === null) {
      setErroDataInstalacao(
        'Informe a data de instalação para iniciar o primeiro refil.',
      )
      dataInstalacaoRef.current?.focus()
      return
    }

    if (fotoModo === 'real' && fotoArquivo === null && dados?.foto_tipo !== 'real') {
      setErroFoto('Escolha a imagem da foto real ou volte à foto padrão.')
      return
    }

    setEnviando(true)
    try {
      if (id) {
        const armadilhaAtualizada = await updateArmadilha(id, {
          identificador,
          modelo_id: modeloId,
          localizacao: parseOptionalValue(formulario.get('localizacao')),
        })
        await aplicarFoto(armadilhaAtualizada.id)
        navigate(`/armadilhas/${encodeURIComponent(armadilhaAtualizada.id)}`)
        return
      }

      const armadilhaCriada = await createArmadilha({
        identificador,
        modelo_id: modeloId,
        localizacao: parseOptionalValue(formulario.get('localizacao')),
        data_instalacao: dataInstalacao,
        criar_refil_inicial: criarRefilInicial,
      })
      try {
        await aplicarFoto(armadilhaCriada.id)
      } catch {
        // A armadilha já existe: leva à edição, onde a foto pode ser reenviada.
        navigate(`/armadilhas/${encodeURIComponent(armadilhaCriada.id)}/editar`, {
          state: {
            avisoFoto:
              'A armadilha foi cadastrada, mas a foto não foi enviada. Escolha a foto de novo e salve.',
          },
        })
        return
      }
      navigate(`/armadilhas/${encodeURIComponent(armadilhaCriada.id)}`)
    } catch (falha: unknown) {
      if (falha instanceof ApiError && falha.codigo === 'IDENTIFICADOR_DUPLICADO') {
        setErroIdentificador(
          'Já existe uma armadilha com este identificador. Escolha outro.',
        )
        identificadorRef.current?.focus()
      } else if (falha instanceof ApiError) {
        setErroEnvio(falha)
      } else {
        setErroEnvio('Não foi possível salvar a armadilha. Tente novamente.')
      }
    } finally {
      setEnviando(false)
    }
  }

  const titulo = id ? 'Editar armadilha' : 'Nova armadilha'

  return (
    <div className="page-stack mx-auto max-w-3xl">
      <header className="page-header">
        <p className="page-kicker">
          Cadastro de equipamento
        </p>
        <h1 className="page-title">
          {titulo}
        </h1>
        <p className="page-description">
          {id
            ? 'Atualize os dados de identificação e localização da armadilha.'
            : 'Informe os dados da armadilha para iniciar o acompanhamento.'}
        </p>
      </header>

      <form
        className="form-panel space-y-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-8"
        key={id ?? 'nova-armadilha'}
        noValidate
        onSubmit={saveArmadilha}
      >
        {avisoFoto ? <MensagemErro erro={avisoFoto} /> : null}
        {erroEnvio ? <MensagemErro erro={erroEnvio} /> : null}
        <CampoFormulario
          descricao="O identificador deve ser único e não pode começar ou terminar com espaços."
          erro={erroIdentificador}
          id="identificador"
          nome="identificador"
          onChange={() => setErroIdentificador(null)}
          obrigatorio
          referencia={identificadorRef}
          rotulo="Identificador"
          valorPadrao={dados?.identificador ?? ''}
        />
        {carregandoModelos ? <EstadoCarregando /> : null}
        {erroModelos ? (
          <div className="space-y-3">
            <MensagemErro
              erro={
                erroModelos instanceof ApiError
                  ? erroModelos
                  : 'Não foi possível carregar os modelos de armadilha.'
              }
            />
            <Botao onClick={recarregarModelos} variante="discreto">
              Tentar novamente
            </Botao>
          </div>
        ) : null}
        {modelos ? (
          <SeletorModelo
            erro={erroModelo}
            modelos={modelos}
            onChange={() => setErroModelo(null)}
            valorPadrao={
              dados?.modelo_id ?? (!id && modelos.length === 1 ? modelos[0].id : null)
            }
          />
        ) : null}
        <CampoFormulario
          id="localizacao"
          nome="localizacao"
          rotulo="Localização"
          valorPadrao={dados?.localizacao ?? ''}
        />
        <CampoFormulario
          descricao={
            id
              ? 'A data de instalação não pode ser alterada depois do cadastro.'
              : 'A data de hoje é preenchida automaticamente para iniciar o primeiro refil.'
          }
          erro={erroDataInstalacao}
          id="data-instalacao"
          nome="data_instalacao"
          onChange={() => setErroDataInstalacao(null)}
          referencia={dataInstalacaoRef}
          rotulo="Data de instalação"
          somenteLeitura={Boolean(id)}
          tipo="date"
          valorPadrao={
            dados?.data_instalacao ?? (id ? '' : localDateIso(new Date()))
          }
        />

        {!id ? (
          <div className="rounded-xl border border-slate-200 bg-stone-50 p-4">
            <label className="flex min-h-11 cursor-pointer items-start gap-3 text-sm font-semibold leading-6 text-slate-900">
              <input
                className="mt-1 size-5 accent-emerald-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-800"
                defaultChecked
                name="criar_refil_inicial"
                onChange={(evento) => {
                  if (!evento.target.checked) setErroDataInstalacao(null)
                }}
                type="checkbox"
              />
              <span>Criar o primeiro refil agora</span>
            </label>
            <p className="ml-8 text-sm leading-6 text-slate-700">
              Sem refil ativo, a armadilha não aceita análises. A data de hoje
              já vem preenchida para iniciar o primeiro refil.
            </p>
          </div>
        ) : null}

        <CampoFotoArmadilha
          arquivo={fotoArquivo}
          erro={erroFoto}
          fotoAtualUrl={dados?.foto_tipo === 'real' ? dados.foto_url : null}
          modo={fotoModo}
          onArquivoChange={(arquivo, erro) => {
            setFotoArquivo(arquivo)
            setErroFoto(erro)
          }}
          onModoChange={(modo) => {
            setFotoModo(modo)
            setErroFoto(null)
            if (modo === 'padrao') setFotoArquivo(null)
          }}
        />

        <div className="flex flex-wrap items-center gap-3 border-t border-slate-200 pt-5">
          <Botao
            disabled={enviando || modelos === null}
            tamanho="amplo"
            type="submit"
            variante="primario"
          >
            {enviando ? 'Salvando…' : id ? 'Salvar alterações' : 'Cadastrar armadilha'}
          </Botao>
          <LinkBotao to={id ? `/armadilhas/${id}` : '/'} variante="discreto">
            Cancelar
          </LinkBotao>
        </div>
      </form>
    </div>
  )
}
