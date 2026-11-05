import { useEffect, useRef } from 'react'
import {
  INTERVALO_GRAVACAO_MS,
  estaInativo,
  lerUltimaAtividade,
  registrarAtividade,
} from '../lib/inatividade'

/** Eventos que contam como uso do aplicativo. */
const EVENTOS_DE_USO = ['pointerdown', 'keydown', 'touchstart', 'wheel', 'scroll'] as const
/** Frequência da conferência enquanto a página está aberta. */
const INTERVALO_CONFERENCIA_MS = 15_000
/** De quanto em quanto tempo o uso renova a sessão no servidor. */
export const INTERVALO_RENOVACAO_MS = 5 * 60 * 1000

/** Encerra a sessão depois de 20 minutos sem uso e mantém o servidor ciente de quem está usando.
 *
 * O tempo é conferido ao voltar para o aplicativo (aba ou app em segundo plano têm os
 * temporizadores suspensos) e a cada 15 s enquanto ele está aberto.
 * @param ativo Liga a vigilância; deve valer só com o usuário autenticado.
 * @param aoExpirar Chamada uma vez quando o limite de inatividade é atingido.
 * @param aoRenovar Chamada, no máximo a cada 5 min, enquanto há uso; renova a sessão no servidor.
 */
export function useInatividade(
  ativo: boolean,
  aoExpirar: () => void,
  aoRenovar: () => void,
): void {
  const aoExpirarRef = useRef(aoExpirar)
  const aoRenovarRef = useRef(aoRenovar)

  useEffect(() => {
    aoExpirarRef.current = aoExpirar
    aoRenovarRef.current = aoRenovar
  })

  useEffect(() => {
    if (!ativo) return undefined

    let ultimaGravacao = 0
    let ultimaRenovacao = Date.now()
    let encerrada = false
    if (lerUltimaAtividade() === null) registrarAtividade()

    const conferir = (): boolean => {
      if (encerrada) return true
      if (estaInativo(lerUltimaAtividade())) {
        encerrada = true
        aoExpirarRef.current()
        return true
      }
      return false
    }

    const aoUsar = () => {
      // Voltar depois de muito tempo e tocar na tela não "ressuscita" a sessão.
      if (conferir()) return
      const agora = Date.now()
      if (agora - ultimaGravacao >= INTERVALO_GRAVACAO_MS) {
        ultimaGravacao = agora
        registrarAtividade(agora)
      }
      if (agora - ultimaRenovacao >= INTERVALO_RENOVACAO_MS) {
        ultimaRenovacao = agora
        aoRenovarRef.current()
      }
    }

    const aoVoltar = () => {
      if (document.visibilityState === 'hidden') return
      conferir()
    }

    EVENTOS_DE_USO.forEach((evento) =>
      window.addEventListener(evento, aoUsar, { capture: true, passive: true }),
    )
    document.addEventListener('visibilitychange', aoVoltar)
    window.addEventListener('focus', aoVoltar)
    window.addEventListener('pageshow', aoVoltar)
    const intervalo = window.setInterval(conferir, INTERVALO_CONFERENCIA_MS)

    return () => {
      EVENTOS_DE_USO.forEach((evento) =>
        window.removeEventListener(evento, aoUsar, { capture: true }),
      )
      document.removeEventListener('visibilitychange', aoVoltar)
      window.removeEventListener('focus', aoVoltar)
      window.removeEventListener('pageshow', aoVoltar)
      window.clearInterval(intervalo)
    }
  }, [ativo])
}
