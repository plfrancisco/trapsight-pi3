import {
  useEffect,
  useId,
  useRef,
  useState,
  type MouseEvent,
  type SyntheticEvent,
} from 'react'
import { deleteUsuario, mensagemDeContas } from '../services/usuarios'
import Botao from './Botao'
import MensagemErro from './MensagemErro'
import { classesBotao } from './botaoStyles'

interface AcaoExcluirContaProps {
  usuarioId: string
  nome: string
  email: string
  onExcluida: () => void
}

/** Confirma a exclusão permanente de um operador antes de chamar a API. */
export default function AcaoExcluirConta({
  usuarioId,
  nome,
  email,
  onExcluida,
}: AcaoExcluirContaProps) {
  const id = useId()
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
    if (enviando) return
    setEnviando(true)
    setErro(null)
    try {
      await deleteUsuario(usuarioId)
      setAberto(false)
      onExcluida()
    } catch (falha: unknown) {
      setErro(mensagemDeContas(falha))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <>
      <button
        aria-label={`Excluir conta de ${nome}`}
        className={classesBotao(
          'discreto',
          'compacto',
          'text-app-danger hover:bg-app-danger-soft focus-visible:outline-app-danger',
        )}
        onClick={abrir}
        ref={(element) => { acionadorRef.current = element }}
        type="button"
      >
        Excluir
      </button>
      <dialog
        aria-describedby={`${id}-descricao-exclusao`}
        aria-labelledby={`${id}-titulo-exclusao`}
        className="m-auto w-[calc(100%-2rem)] max-w-lg rounded-2xl border border-red-200 bg-white p-0 text-slate-950 shadow-2xl backdrop:bg-slate-950/45"
        onCancel={cancelar}
        ref={dialogoRef}
      >
        {aberto ? (
        <div className="space-y-4 p-5 sm:p-6">
          <div>
            <p className="text-xs font-bold text-app-danger">Exclusão permanente</p>
            <h2 className="mt-2 text-xl font-semibold" id={`${id}-titulo-exclusao`}>
              Excluir a conta de {nome}?
            </h2>
            <p className="mt-2 break-all text-sm font-medium text-slate-700">{email}</p>
            <p
              className="mt-2 text-sm leading-6 text-slate-700"
              id={`${id}-descricao-exclusao`}
            >
              A pessoa perderá o acesso imediatamente e as sessões abertas serão removidas. Essa ação não pode ser desfeita.
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
              {enviando ? 'Excluindo…' : 'Confirmar exclusão'}
            </Botao>
          </div>
        </div>
        ) : null}
      </dialog>
    </>
  )
}
