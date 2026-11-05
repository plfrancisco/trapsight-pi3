import { useCallback, useEffect, useState } from 'react'
import { gravarCache, lerCache } from '../lib/cacheLocal'

interface Carregamento<T> {
  dados: T | null
  erro: unknown | null
  carregando: boolean
  recarregar: () => void
}

/** Guarda a última resposta para a tela abrir já preenchida e ser atualizada por baixo. */
interface OpcoesCache<T> {
  /** Nome do dado no cache local; é apagado no logout e na inatividade. */
  chave: string
  /** Confere o formato do que foi guardado; o que não passa é ignorado. */
  validar: (valor: unknown) => valor is T
}

/**
 * Carrega dados com cancelamento quando as dependências mudam ou o componente
 * desmonta.
 *
 * Mantenha a função estável com useCallback e inclua nela os valores usados.
 * @param carregar Função assíncrona que recebe o sinal de cancelamento atual.
 * @param cache Opcional: mostra a última resposta guardada enquanto a nova não chega.
 * @returns Dados, falha, estado de carregamento e ação para repetir a consulta.
 */
export function useCarregamento<T>(
  carregar: (signal: AbortSignal) => Promise<T>,
  cache?: OpcoesCache<T>,
): Carregamento<T> {
  const [dados, setDados] = useState<T | null>(() =>
    cache ? lerCache(cache.chave, cache.validar) : null,
  )
  const [erro, setErro] = useState<unknown | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [numeroRecargas, setNumeroRecargas] = useState(0)
  const recarregar = useCallback(() => setNumeroRecargas((valor) => valor + 1), [])
  const chaveCache = cache?.chave

  useEffect(() => {
    const controlador = new AbortController()

    const executar = async () => {
      try {
        await Promise.resolve()
        if (controlador.signal.aborted) return
        setCarregando(true)
        setErro(null)
        const resultado = await carregar(controlador.signal)
        if (!controlador.signal.aborted) {
          setDados(resultado)
          if (chaveCache) gravarCache(chaveCache, resultado)
        }
      } catch (falha: unknown) {
        if (!controlador.signal.aborted) setErro(falha)
      } finally {
        if (!controlador.signal.aborted) setCarregando(false)
      }
    }

    void executar()

    return () => controlador.abort()
  }, [carregar, chaveCache, numeroRecargas])

  return { dados, erro, carregando, recarregar }
}
