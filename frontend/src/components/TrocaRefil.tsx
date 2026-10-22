import { useEffect, useRef, useState, type MouseEvent, type SyntheticEvent } from 'react'
import { localDateIso } from '../lib/datas'
import { ApiError } from '../services/erros'
import { replaceRefil } from '../services/armadilhas'
import Botao from './Botao'
import MensagemErro from './MensagemErro'

interface TrocaRefilProps {
  armadilhaId: string
  temRefilAtivo: boolean
  onConcluir: () => void
}

/** Confirma e registra uma troca de refil sem descartar os dados da página.
 * @param props Identificador da armadilha, estado do refil e ação de recarga.
 * @returns Ação e diálogo modal de confirmação da troca.
 */
export default function TrocaRefil({
  armadilhaId,
  temRefilAtivo,
  onConcluir,
}: TrocaRefilProps) {
  const [confirmando, setConfirmando] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const referenciaDialogo = useRef<HTMLDialogElement>(null)
  const referenciaAcionador = useRef<HTMLButtonElement | null>(null)

  useEffect(() => {
    const dialogo = referenciaDialogo.current
    if (!dialogo) return

    if (confirmando && !dialogo.open) {
      dialogo.showModal()
      dialogo.querySelector<HTMLButtonElement>('[data-foco-seguro]')?.focus()
    } else if (!confirmando && dialogo.open) {
      dialogo.close()
      referenciaAcionador.current?.focus()
    }
  }, [confirmando])

  function abrirConfirmacao(event: MouseEvent<HTMLButtonElement>) {
    referenciaAcionador.current = event.currentTarget
    setErro(null)
    setConfirmando(true)
  }

  function fecharConfirmacao() {
    if (enviando) return
    setErro(null)
    setConfirmando(false)
  }

  function handleCancel(event: SyntheticEvent<HTMLDialogElement>) {
    event.preventDefault()
    fecharConfirmacao()
  }

  async function confirmTroca() {
    setEnviando(true)
    setErro(null)
    try {
      await replaceRefil(armadilhaId, {
        data_instalacao: localDateIso(new Date()),
      })
      setConfirmando(false)
      onConcluir()
    } catch (falha: unknown) {
      setErro(
        falha instanceof ApiError
          ? falha.mensagem
          : 'Não foi possível registrar a troca do refil.',
      )
    } finally {
      setEnviando(false)
    }
  }

  return (
    <section aria-label="Troca de refil" className="space-y-3">
      <Botao
        disabled={enviando}
        onClick={abrirConfirmacao}
        variante="primario"
      >
        {temRefilAtivo ? 'Registrar troca de refil' : 'Registrar refil'}
      </Botao>
      <dialog
        aria-describedby="descricao-confirmacao-troca"
        aria-labelledby="titulo-confirmacao-troca"
        className="m-auto w-[calc(100%-2rem)] max-w-xl rounded-2xl border border-amber-300 bg-amber-50 p-0 text-slate-950 shadow-xl backdrop:bg-slate-950/50"
        onCancel={handleCancel}
        ref={referenciaDialogo}
      >
        <div className="space-y-4 p-5">
          <div>
            <h2
              className="text-lg font-semibold text-slate-950"
              id="titulo-confirmacao-troca"
            >
              Confirmar troca de refil
            </h2>
            <p
              className="mt-2 text-sm leading-6 text-slate-800"
              id="descricao-confirmacao-troca"
            >
              Encerrar o refil atual e iniciar um novo hoje? A série de medições
              recomeça do zero.
            </p>
          </div>
          {erro ? <MensagemErro erro={erro} /> : null}
          <div className="flex flex-wrap gap-2">
            <Botao
              disabled={enviando}
              onClick={() => void confirmTroca()}
              variante="primario"
            >
              {enviando ? 'Registrando…' : 'Confirmar troca'}
            </Botao>
            <Botao
              data-foco-seguro
              disabled={enviando}
              onClick={fecharConfirmacao}
              variante="secundario"
            >
              Cancelar
            </Botao>
          </div>
        </div>
      </dialog>
    </section>
  )
}
