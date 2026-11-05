import { useEffect, useRef, useState } from 'react'
import { detectarCelular, useInstalacao } from '../hooks/useInstalacao'
import MarcaTrapSight from './MarcaTrapSight'

const CHAVE_DISPENSA_EM = 'trapsight:tela-instalacao-dispensada-em'
const SETE_DIAS_EM_MS = 7 * 24 * 60 * 60 * 1000

function dispensadaRecentemente(): boolean {
  try {
    const gravado = Number(window.localStorage.getItem(CHAVE_DISPENSA_EM))
    return Number.isFinite(gravado) && gravado > 0 && Date.now() - gravado < SETE_DIAS_EM_MS
  } catch {
    return false
  }
}

/** Convida quem abre o site no celular a instalar o aplicativo, em tela cheia.
 * Reaparece 7 dias depois de dispensada; nunca bloqueia o uso pelo navegador.
 * @returns A tela de instalação ou `null` fora do celular, já instalado ou sem suporte.
 */
export default function TelaInstalacao() {
  const { podeInstalar, instalado, ehIos, instalar } = useInstalacao()
  const [dispensada, setDispensada] = useState(dispensadaRecentemente)
  const botaoPrincipal = useRef<HTMLButtonElement>(null)
  const visivel = detectarCelular() && !instalado && !dispensada && (ehIos || podeInstalar)

  useEffect(() => {
    if (!visivel) return
    botaoPrincipal.current?.focus()
  }, [visivel])

  if (!visivel) return null

  function dispensar() {
    setDispensada(true)
    try {
      window.localStorage.setItem(CHAVE_DISPENSA_EM, String(Date.now()))
    } catch {
      // Sem armazenamento, a tela só deixa de aparecer enquanto a página estiver aberta.
    }
  }

  return (
    <div
      aria-labelledby="titulo-tela-instalacao"
      aria-modal="true"
      className="fixed inset-0 z-[100] flex flex-col overflow-y-auto bg-app-surface px-6 pb-8 pt-10 text-app-foreground"
      onKeyDown={(evento) => {
        if (evento.key === 'Escape') dispensar()
      }}
      role="dialog"
    >
      <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center text-center">
        <div className="flex justify-center">
          <MarcaTrapSight />
        </div>
        <h2 className="mt-8 text-2xl font-semibold" id="titulo-tela-instalacao">
          Instale o TrapSight
        </h2>
        <p className="mt-3 text-sm leading-6 text-app-muted">
          Abra o monitoramento direto da tela inicial do celular, em tela cheia e sem digitar o endereço.
        </p>

        {ehIos ? (
          <ol className="mt-6 space-y-3 rounded-2xl border border-app-border bg-app-soft p-4 text-left text-sm leading-6">
            <li><span className="font-semibold">1.</span> No Safari, toque em <strong>Compartilhar</strong>.</li>
            <li><span className="font-semibold">2.</span> Escolha <strong>Adicionar à Tela de Início</strong>.</li>
            <li><span className="font-semibold">3.</span> Toque em <strong>Adicionar</strong>.</li>
          </ol>
        ) : (
          <button
            className="mt-8 inline-flex min-h-12 w-full items-center justify-center rounded-xl bg-app-primary px-4 text-base font-semibold text-app-on-primary transition-colors hover:bg-app-primary-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-primary"
            onClick={() => void instalar()}
            ref={botaoPrincipal}
            type="button"
          >
            Instalar aplicativo
          </button>
        )}

        <button
          className="mt-4 inline-flex min-h-11 items-center justify-center rounded-xl px-4 text-sm font-medium text-app-muted underline underline-offset-4 transition-colors hover:text-app-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-primary"
          onClick={dispensar}
          ref={ehIos ? botaoPrincipal : undefined}
          type="button"
        >
          Continuar no navegador
        </button>
      </div>
    </div>
  )
}
