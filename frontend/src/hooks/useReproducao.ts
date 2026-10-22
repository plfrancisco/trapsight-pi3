import { useCallback, useEffect, useRef, useState } from 'react'
import { limitarVelocidade, proximoIndice } from '../lib/timelapse'

interface ReproducaoTimelapse {
  indiceQuadro: number
  reproduzindo: boolean
  playTimelapse: () => void
  pauseTimelapse: () => void
  changeQuadro: (indice: number) => void
}

/** Controla o avanço temporizado dos quadros sem repetir o último.
 * @param quantidadeQuadros Total de análises disponíveis no escopo.
 * @param velocidadeMs Intervalo desejado em milissegundos por quadro.
 * @returns Índice atual e ações para reproduzir, pausar ou selecionar um quadro.
 */
export function useReproducao(
  quantidadeQuadros: number,
  velocidadeMs: number,
): ReproducaoTimelapse {
  const [indiceQuadro, setIndiceQuadro] = useState(0)
  const [reproduzindo, setReproduzindo] = useState(false)
  const montado = useRef(false)

  useEffect(() => {
    montado.current = true
    return () => {
      montado.current = false
    }
  }, [])

  useEffect(() => {
    if (!reproduzindo || quantidadeQuadros < 2) return

    const indiceSeguinte = proximoIndice(indiceQuadro, quantidadeQuadros)
    if (indiceSeguinte === null) {
      const temporizador = window.setTimeout(() => {
        if (montado.current) setReproduzindo(false)
      }, 0)
      return () => window.clearTimeout(temporizador)
    }

    const temporizador = window.setTimeout(() => {
      if (!montado.current) return
      setIndiceQuadro(indiceSeguinte)
      if (indiceSeguinte === quantidadeQuadros - 1) setReproduzindo(false)
    }, limitarVelocidade(velocidadeMs))

    return () => window.clearTimeout(temporizador)
  }, [indiceQuadro, quantidadeQuadros, reproduzindo, velocidadeMs])

  const playTimelapse = useCallback(() => {
    if (quantidadeQuadros < 2) return
    if (indiceQuadro >= quantidadeQuadros - 1) setIndiceQuadro(0)
    setReproduzindo(true)
  }, [indiceQuadro, quantidadeQuadros])

  const pauseTimelapse = useCallback(() => {
    setReproduzindo(false)
  }, [])

  const changeQuadro = useCallback(
    (indice: number) => {
      const indiceSeguro = Number.isFinite(indice) ? Math.trunc(indice) : 0
      const maiorIndice = Math.max(0, quantidadeQuadros - 1)
      setIndiceQuadro(Math.max(0, Math.min(maiorIndice, indiceSeguro)))
      setReproduzindo(false)
    },
    [quantidadeQuadros],
  )

  return {
    indiceQuadro,
    reproduzindo,
    playTimelapse,
    pauseTimelapse,
    changeQuadro,
  }
}
