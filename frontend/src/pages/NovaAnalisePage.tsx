import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
} from 'react'
import Botao from '../components/Botao'
import CabecalhoNovaAnalise from '../components/CabecalhoNovaAnalise'
import EnvioAnalise from '../components/EnvioAnalise'
import ResultadoAnalise from '../components/ResultadoAnalise'
import SeletorArmadilha from '../components/SeletorArmadilha'
import {
  buildFalhaMensagem,
  findArmadilha,
  isAbortError,
  validateArquivoAnalise,
} from '../lib/analise'
import { useCarregamento } from '../hooks/useCarregamento'
import { createAnalise } from '../services/analises'
import { listArmadilhas } from '../services/armadilhas'
import { TIMEOUT_UPLOAD_MS } from '../services/http'
import type { Analise } from '../services/tipos'

/** Seleciona uma armadilha, envia uma imagem e mostra o resultado da inferência.
 * @returns O fluxo de seleção, envio ou resultado da análise.
 */
export default function NovaAnalisePage() {
  const loadArmadilhas = useCallback(
    (signal: AbortSignal) => listArmadilhas(signal),
    [],
  )
  const {
    dados: armadilhas,
    erro: erroCarregamento,
    carregando,
    recarregar: reload,
  } = useCarregamento(loadArmadilhas)
  const [armadilhaId, setArmadilhaId] = useState('')
  const [arquivo, setArquivo] = useState<File | null>(null)
  const [erroArquivo, setErroArquivo] = useState<string | null>(null)
  const [erroAnalise, setErroAnalise] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)
  const [resultado, setResultado] = useState<Analise | null>(null)
  const controladorEnvio = useRef<AbortController | null>(null)
  const armadilhaSelecionada = findArmadilha(armadilhas, armadilhaId)
  const semRefilAtivo = armadilhaSelecionada?.refil_ativo === null

  useEffect(() => () => controladorEnvio.current?.abort(), [])

  const changeArquivo = (evento: ChangeEvent<HTMLInputElement>) => {
    const proximoArquivo = evento.currentTarget.files?.[0] ?? null
    setErroAnalise(null)
    setArquivo(proximoArquivo)
    setErroArquivo(proximoArquivo ? validateArquivoAnalise(proximoArquivo) : null)
  }

  const sendAnalise = async (evento: FormEvent<HTMLFormElement>) => {
    evento.preventDefault()
    if (!armadilhaSelecionada || semRefilAtivo || !arquivo || erroArquivo) return

    const controlador = new AbortController()
    controladorEnvio.current = controlador
    setEnviando(true)
    setErroAnalise(null)
    setResultado(null)

    try {
      const analise = await createAnalise(
        armadilhaSelecionada.id,
        arquivo,
        controlador.signal,
      )
      setResultado(analise)
    } catch (falha: unknown) {
      if (!controlador.signal.aborted && !isAbortError(falha)) {
        setErroAnalise(buildFalhaMensagem(falha))
      }
    } finally {
      if (controladorEnvio.current === controlador) {
        controladorEnvio.current = null
      }
      setEnviando(false)
    }
  }

  const resetAnalise = () => {
    setResultado(null)
    setErroAnalise(null)
    setErroArquivo(null)
    setArquivo(null)
    setArmadilhaId('')
  }

  if (resultado) {
    return (
      <div className="mx-auto max-w-5xl space-y-8">
        <CabecalhoNovaAnalise />
        <div className="space-y-5">
          <ResultadoAnalise analise={resultado} />
          <Botao onClick={resetAnalise} tamanho="amplo" variante="primario">
            Nova análise
          </Botao>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <CabecalhoNovaAnalise />
      <SeletorArmadilha
        armadilhas={armadilhas}
        carregando={carregando}
        erro={erroCarregamento}
        onRetry={reload}
      >
        <EnvioAnalise
          armadilhas={armadilhas ?? []}
          armadilhaId={armadilhaId}
          armadilhaSelecionada={armadilhaSelecionada}
          arquivo={arquivo}
          erroArquivo={erroArquivo}
          erroAnalise={erroAnalise}
          enviando={enviando}
          onCancel={() => controladorEnvio.current?.abort()}
          onChangeArmadilha={(evento) => {
            setArmadilhaId(evento.currentTarget.value)
            setErroAnalise(null)
          }}
          onChangeArquivo={changeArquivo}
          onSubmit={sendAnalise}
          timeoutUploadMs={TIMEOUT_UPLOAD_MS}
        />
      </SeletorArmadilha>
    </div>
  )
}
