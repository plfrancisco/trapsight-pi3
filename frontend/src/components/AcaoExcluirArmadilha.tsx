import { useEffect, useRef, useState, type MouseEvent, type SyntheticEvent } from 'react'
import { useNavigate } from 'react-router'
import { ApiError } from '../services/erros'
import { deleteArmadilha } from '../services/armadilhas'
import { classesBotao } from './botaoStyles'
import Botao from './Botao'
import MensagemErro from './MensagemErro'

interface AcaoExcluirArmadilhaProps {
  armadilhaId: string
  identificador: string
}

/** Confirma a remoção lógica e mantém visível o destino dos dados históricos. */
export default function AcaoExcluirArmadilha({
  armadilhaId,
  identificador,
}: AcaoExcluirArmadilhaProps) {
  const navigate = useNavigate()
  const [aberto, setAberto] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const dialogoRef = useRef<HTMLDialogElement>(null)
  const acionadorRef = useRef<HTMLButtonElement | null>(null)

  useEffect(() => {
    const dialogo = dialogoRef.current
    if (!dialogo) return
    if (aberto && !dialogo.open) {
      dialogo.showModal()
      dialogo.querySelector<HTMLButtonElement>('[data-foco-seguro]')?.focus()
    } else if (!aberto && dialogo.open) {
      dialogo.close()
      acionadorRef.current?.focus()
    }
  }, [aberto])

  function abrir(evento: MouseEvent<HTMLButtonElement>) {
    acionadorRef.current = evento.currentTarget
    setErro(null)
    setAberto(true)
  }

  function fechar() {
    if (enviando) return
    setErro(null)
    setAberto(false)
  }

  function cancelar(evento: SyntheticEvent<HTMLDialogElement>) {
    evento.preventDefault()
    fechar()
  }

  async function confirmar() {
    setEnviando(true)
    setErro(null)
    try {
      await deleteArmadilha(armadilhaId)
      setAberto(false)
      navigate('/')
    } catch (falha: unknown) {
      setErro(
        falha instanceof ApiError
          ? falha.mensagem
          : 'Não foi possível remover a armadilha. Tente novamente.',
      )
    } finally {
      setEnviando(false)
    }
  }

  return (
    <>
      <button
        className={classesBotao(
          'discreto',
          'padrao',
          'text-red-700 hover:bg-red-50 focus-visible:outline-red-600',
        )}
        onClick={abrir}
        ref={(element) => { acionadorRef.current = element }}
        type="button"
      >
        Excluir armadilha
      </button>
      <dialog
        aria-describedby="descricao-exclusao-armadilha"
        aria-labelledby="titulo-exclusao-armadilha"
        className="m-auto w-[calc(100%-2rem)] max-w-lg rounded-2xl border border-red-200 bg-white p-0 text-slate-950 shadow-2xl backdrop:bg-slate-950/45"
        onCancel={cancelar}
        ref={dialogoRef}
      >
        <div className="space-y-4 p-5 sm:p-6">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-red-700">
              Remover equipamento
            </p>
            <h2 className="mt-2 text-xl font-semibold" id="titulo-exclusao-armadilha">
              Remover {identificador} do painel?
            </h2>
            <p className="mt-2 text-sm leading-6 text-slate-700" id="descricao-exclusao-armadilha">
              A armadilha deixa de aparecer no painel e não aceitará novas análises ou trocas de refil. As análises e os históricos de refil continuarão salvos e poderão ser consultados.
            </p>
          </div>
          {erro ? <MensagemErro erro={erro} /> : null}
          <div className="flex flex-wrap justify-end gap-2 border-t border-slate-100 pt-4">
            <Botao
              data-foco-seguro
              disabled={enviando}
              onClick={fechar}
              variante="secundario"
            >
              Cancelar
            </Botao>
            <Botao
              className="bg-red-700 text-white hover:bg-red-800 focus-visible:outline-red-700"
              disabled={enviando}
              onClick={() => void confirmar()}
              variante="primario"
            >
              {enviando ? 'Removendo…' : 'Confirmar remoção'}
            </Botao>
          </div>
        </div>
      </dialog>
    </>
  )
}
