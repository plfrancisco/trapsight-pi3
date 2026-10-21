import { useRef, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { localDateIso } from '../lib/datas'
import { ApiError } from '../services/erros'
import { createArmadilha, updateArmadilha } from '../services/armadilhas'
import type { ArmadilhaDetalhe } from '../services/tipos'
import Botao from './Botao'
import CampoFormulario from './CampoFormulario'
import LinkBotao from './LinkBotao'
import MensagemErro from './MensagemErro'

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
  const identificadorRef = useRef<HTMLInputElement>(null)
  const dataInstalacaoRef = useRef<HTMLInputElement>(null)
  const [erroIdentificador, setErroIdentificador] = useState<string | null>(null)
  const [erroDataInstalacao, setErroDataInstalacao] = useState<string | null>(null)
  const [erroEnvio, setErroEnvio] = useState<ApiError | string | null>(null)
  const [enviando, setEnviando] = useState(false)

  const saveArmadilha = async (evento: FormEvent<HTMLFormElement>) => {
    evento.preventDefault()
    setErroIdentificador(null)
    setErroDataInstalacao(null)
    setErroEnvio(null)

    const formulario = new FormData(evento.currentTarget)
    const identificador = String(formulario.get('identificador') ?? '').trim()
    if (!identificador) {
      setErroIdentificador('Informe o identificador da armadilha.')
      identificadorRef.current?.focus()
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

    setEnviando(true)
    try {
      if (id) {
        const armadilhaAtualizada = await updateArmadilha(id, {
          identificador,
          modelo: parseOptionalValue(formulario.get('modelo')),
          localizacao: parseOptionalValue(formulario.get('localizacao')),
        })
        navigate(`/armadilhas/${encodeURIComponent(armadilhaAtualizada.id)}`)
        return
      }

      const armadilhaCriada = await createArmadilha({
        identificador,
        modelo: parseOptionalValue(formulario.get('modelo')),
        localizacao: parseOptionalValue(formulario.get('localizacao')),
        data_instalacao: dataInstalacao,
        criar_refil_inicial: criarRefilInicial,
      })
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
    <div className="mx-auto max-w-3xl space-y-8">
      <header>
        <p className="text-sm font-semibold uppercase tracking-[0.14em] text-emerald-900">
          Cadastro de equipamento
        </p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">
          {titulo}
        </h1>
        <p className="mt-3 max-w-2xl text-base leading-7 text-slate-700">
          {id
            ? 'Atualize os dados de identificação e localização da armadilha.'
            : 'Informe os dados da armadilha para iniciar o acompanhamento.'}
        </p>
      </header>

      <form
        className="space-y-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-8"
        key={id ?? 'nova-armadilha'}
        noValidate
        onSubmit={saveArmadilha}
      >
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
        <CampoFormulario
          id="modelo"
          nome="modelo"
          rotulo="Modelo"
          valorPadrao={dados?.modelo ?? ''}
        />
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

        <div className="flex flex-wrap items-center gap-3 border-t border-slate-200 pt-5">
          <Botao
            disabled={enviando}
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
