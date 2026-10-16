import { useCallback, useEffect, useState } from 'react'

interface Carregamento<T> {
  dados: T | null
  erro: unknown | null
  carregando: boolean
  recarregar: () => void
}

/**
 * Carrega dados com cancelamento quando as dependências mudam ou o componente
 * desmonta.
 *
 * Mantenha a função estável com useCallback e inclua nela os valores usados.
 * @param carregar Função assíncrona que recebe o sinal de cancelamento atual.
 * @returns Dados, falha, estado de carregamento e ação para repetir a consulta.
 */
export function useCarregamento<T>(carregar: (signal: AbortSignal) => Promise<T>): Carregamento<T> {
  const [dados, setDados] = useState<T | null>(null)
  const [erro, setErro] = useState<unknown | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [numeroRecargas, setNumeroRecargas] = useState(0)
  const recarregar = useCallback(() => setNumeroRecargas((valor) => valor + 1), [])

  useEffect(() => {
    const controlador = new AbortController()

    const executar = async () => {
      try {
        await Promise.resolve()
        if (controlador.signal.aborted) return
        setCarregando(true)
        setErro(null)
        const resultado = await carregar(controlador.signal)
        if (!controlador.signal.aborted) setDados(resultado)
      } catch (falha: unknown) {
        if (!controlador.signal.aborted) setErro(falha)
      } finally {
        if (!controlador.signal.aborted) setCarregando(false)
      }
    }

    void executar()

    return () => controlador.abort()
  }, [carregar, numeroRecargas])

  return { dados, erro, carregando, recarregar }
}
