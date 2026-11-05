import { useEffect, useState } from 'react'
import { useInstalacao } from '../hooks/useInstalacao'

const CHAVE_DISPENSA = 'trapsight:convite-instalacao-dispensado'
const CONSULTA_CELULAR = '(max-width: 767px)'

function lerSeEhCelular(): boolean {
  if (typeof window === 'undefined') return false

  try {
    return window.matchMedia(CONSULTA_CELULAR).matches
  } catch {
    return false
  }
}

function lerDispensa(): boolean {
  if (typeof window === 'undefined') return false

  try {
    return window.localStorage.getItem(CHAVE_DISPENSA) === 'true'
  } catch {
    return false
  }
}

/** Convida usuários de celular a instalar o aplicativo sem interromper o login.
 * @returns A faixa de instalação ou `null` quando a plataforma não oferece o fluxo.
 */
export default function ConviteInstalacao() {
  const { podeInstalar, instalado, ehIos, instalar } = useInstalacao()
  const [ehCelular, setEhCelular] = useState(lerSeEhCelular)
  const [dispensada, setDispensada] = useState(lerDispensa)

  useEffect(() => {
    const consulta = window.matchMedia?.(CONSULTA_CELULAR)
    if (!consulta) return

    const atualizarLargura = () => setEhCelular(consulta.matches)

    if (consulta.addEventListener) {
      consulta.addEventListener('change', atualizarLargura)
      return () => consulta.removeEventListener('change', atualizarLargura)
    }

    consulta.addListener?.(atualizarLargura)
    return () => consulta.removeListener?.(atualizarLargura)
  }, [])

  if (!ehCelular || instalado || dispensada || (!ehIos && !podeInstalar)) {
    return null
  }

  function dispensar() {
    setDispensada(true)

    try {
      window.localStorage.setItem(CHAVE_DISPENSA, 'true')
    } catch {
      // A faixa continua dispensada nesta sessão mesmo quando o navegador bloqueia armazenamento.
    }
  }

  return (
    <aside
      aria-label="Instalar o TrapSight"
      className="mt-6 flex items-start gap-3 rounded-2xl border border-app-border bg-app-soft p-3 text-app-foreground"
    >
      <span aria-hidden="true" className="mt-0.5 grid size-10 shrink-0 place-items-center rounded-xl bg-app-primary-soft text-app-primary">
        <svg fill="none" viewBox="0 0 24 24" className="size-5">
          <path d="M12 3v11m0 0 4-4m-4 4-4-4M5 16v3a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-3" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.7" />
        </svg>
      </span>

      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold">Tenha o TrapSight na tela inicial</p>
        {ehIos ? (
          <p className="mt-1 text-xs leading-5 text-app-muted">
            No Safari, toque em Compartilhar e depois em Adicionar à Tela de Início.
          </p>
        ) : (
          <p className="mt-1 text-xs leading-5 text-app-muted">
            Instale para abrir o monitoramento direto pela tela inicial.
          </p>
        )}
        {podeInstalar ? (
          <button
            className="mt-2 inline-flex min-h-11 items-center rounded-xl bg-app-primary px-4 text-sm font-semibold text-app-on-primary transition-colors hover:bg-app-primary-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-primary"
            onClick={() => void instalar()}
            type="button"
          >
            Instalar
          </button>
        ) : null}
      </div>

      <button
        aria-label="Dispensar convite de instalação"
        className="grid size-11 shrink-0 place-items-center rounded-xl text-app-muted transition-colors hover:bg-app-surface hover:text-app-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-primary"
        onClick={dispensar}
        type="button"
      >
        <svg aria-hidden="true" fill="none" viewBox="0 0 20 20" className="size-4">
          <path d="m5 5 10 10M15 5 5 15" stroke="currentColor" strokeLinecap="round" strokeWidth="1.7" />
        </svg>
      </button>
    </aside>
  )
}
