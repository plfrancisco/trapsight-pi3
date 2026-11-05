import { useCallback, useEffect, useState, useSyncExternalStore } from 'react'

const CONSULTA_MODO_INSTALADO = '(display-mode: standalone)'

interface EscolhaDoPrompt {
  outcome: 'accepted' | 'dismissed'
  platform: string
}

interface EventoAntesDeInstalar extends Event {
  readonly platforms: string[]
  readonly userChoice: Promise<EscolhaDoPrompt>
  prompt(): Promise<void>
}

interface NavegadorIos extends Navigator {
  standalone?: boolean
}

let eventoDeInstalacaoPendente: EventoAntesDeInstalar | null = null
const ouvintesDoEvento = new Set<() => void>()

function notificarEventoDeInstalacao() {
  ouvintesDoEvento.forEach((ouvinte) => ouvinte())
}

function assinarEventoDeInstalacao(ouvinte: () => void) {
  ouvintesDoEvento.add(ouvinte)
  return () => ouvintesDoEvento.delete(ouvinte)
}

function lerEventoDeInstalacao() {
  return eventoDeInstalacaoPendente
}

function capturarConviteDeInstalacao(evento: Event) {
  const eventoDeInstalacao = evento as EventoAntesDeInstalar
  if (typeof eventoDeInstalacao.prompt !== 'function') return

  evento.preventDefault()
  eventoDeInstalacaoPendente = eventoDeInstalacao
  notificarEventoDeInstalacao()
}

function limparConviteDeInstalacao() {
  eventoDeInstalacaoPendente = null
  notificarEventoDeInstalacao()
}

if (typeof window !== 'undefined') {
  // O convite pode chegar antes da tela de configurações abrir; mantê-lo aqui permite usá-lo depois da navegação.
  window.addEventListener('beforeinstallprompt', capturarConviteDeInstalacao)
  window.addEventListener('appinstalled', limparConviteDeInstalacao)
}

function lerModoInstalado(): boolean {
  if (typeof window === 'undefined') return false

  const navegador = window.navigator as NavegadorIos
  const instaladoNoIos = navegador.standalone === true

  try {
    return instaladoNoIos || window.matchMedia(CONSULTA_MODO_INSTALADO).matches
  } catch {
    return instaladoNoIos
  }
}

function detectarIos(): boolean {
  if (typeof navigator === 'undefined') return false

  const userAgent = navigator.userAgent
  // O Safari pode identificar um iPad em modo desktop como Mac; o toque diferencia esse caso.
  return /iPad|iPhone|iPod/i.test(userAgent)
    || (/Macintosh/i.test(userAgent) && navigator.maxTouchPoints > 1)
}

/** Informa se o site está aberto como aplicativo instalado e acompanha mudanças do navegador.
 * @returns `true` quando o modo standalone ou o indicador de instalação do Safari está ativo.
 */
export function useModoInstalado(): boolean {
  const [instalado, setInstalado] = useState(lerModoInstalado)

  useEffect(() => {
    if (typeof window === 'undefined') return

    const atualizarModo = () => setInstalado(lerModoInstalado())
    const marcarComoInstalado = () => setInstalado(true)
    const consulta = window.matchMedia?.(CONSULTA_MODO_INSTALADO)

    if (consulta?.addEventListener) {
      consulta.addEventListener('change', atualizarModo)
    } else {
      consulta?.addListener?.(atualizarModo)
    }
    window.addEventListener('appinstalled', marcarComoInstalado)

    return () => {
      if (consulta?.removeEventListener) {
        consulta.removeEventListener('change', atualizarModo)
      } else {
        consulta?.removeListener?.(atualizarModo)
      }
      window.removeEventListener('appinstalled', marcarComoInstalado)
    }
  }, [])

  return instalado
}

/** Expõe o convite nativo de instalação e o passo manual disponível no iOS.
 * @returns A disponibilidade da instalação, o estado instalado, a plataforma e a ação de instalar.
 */
export function useInstalacao() {
  const modoInstalado = useModoInstalado()
  const ehIos = detectarIos()
  const evento = useSyncExternalStore(
    assinarEventoDeInstalacao,
    lerEventoDeInstalacao,
    () => null,
  )
  const [instaladoAposAceite, setInstaladoAposAceite] = useState(false)

  const instalado = modoInstalado || instaladoAposAceite

  const instalar = useCallback(async () => {
    if (!evento) return

    limparConviteDeInstalacao()

    try {
      await evento.prompt()
      const escolha = await evento.userChoice
      if (escolha.outcome === 'accepted') setInstaladoAposAceite(true)
    } catch {
      // O navegador consome o convite após a interação e pode rejeitar a abertura do diálogo.
    }
  }, [evento])

  return {
    podeInstalar: Boolean(evento) && !instalado && !ehIos,
    instalado,
    ehIos,
    instalar,
  }
}
