import { act, renderHook, waitFor } from '@testing-library/react'
import { useCallback } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { useCarregamento } from './useCarregamento'

interface PromessaPendente<T> {
  promise: Promise<T>
  resolver: (valor: T) => void
  rejeitar: (erro: unknown) => void
}

function criarPromessaPendente<T>(): PromessaPendente<T> {
  let resolver!: (valor: T) => void
  let rejeitar!: (erro: unknown) => void
  const promise = new Promise<T>((resolve, reject) => {
    resolver = resolve
    rejeitar = reject
  })
  return { promise, resolver, rejeitar }
}

describe('useCarregamento', () => {
  it('carrega e expõe os dados quando a consulta tem sucesso', async () => {
    const carregar = vi.fn(async () => ['arm-1', 'arm-2'])
    const { result } = renderHook(() => useCarregamento(carregar))

    expect(result.current.carregando).toBe(true)
    await waitFor(() => expect(result.current.dados).toEqual(['arm-1', 'arm-2']))
    expect(result.current.carregando).toBe(false)
    expect(result.current.erro).toBeNull()
    expect(carregar).toHaveBeenCalledWith(expect.any(AbortSignal))
  })

  it('guarda a falha da consulta para a tela apresentar', async () => {
    const falha = new Error('falha de consulta')
    const carregar = () => Promise.reject(falha)
    const { result } = renderHook(() => useCarregamento(carregar))

    await waitFor(() => expect(result.current.erro).toBe(falha))
    expect(result.current.carregando).toBe(false)
  })

  it('cancela a consulta quando o componente desmonta', async () => {
    const pendente = criarPromessaPendente<string>()
    let sinal: AbortSignal | undefined
    const carregar = (novoSinal: AbortSignal) => {
      sinal = novoSinal
      return pendente.promise
    }
    const { result, unmount } = renderHook(() => useCarregamento(carregar))

    await waitFor(() => expect(sinal).toBeDefined())
    unmount()
    expect(sinal?.aborted).toBe(true)

    await act(async () => {
      pendente.resolver('resultado obsoleto')
      await pendente.promise
    })
    expect(result.current.dados).toBeNull()
  })

  it('ignora uma resposta antiga quando as dependências mudam', async () => {
    const requisicoes = new Map<
      string,
      { sinal: AbortSignal; pendente: PromessaPendente<string> }
    >()
    const { result, rerender } = renderHook(
      ({ armadilhaId }: { armadilhaId: string }) => {
        const carregar = useCallback((sinal: AbortSignal) => {
          const pendente = criarPromessaPendente<string>()
          requisicoes.set(armadilhaId, { sinal, pendente })
          return pendente.promise
        }, [armadilhaId])
        return useCarregamento(carregar)
      },
      { initialProps: { armadilhaId: 'arm-1' } },
    )

    await waitFor(() => expect(requisicoes.has('arm-1')).toBe(true))
    rerender({ armadilhaId: 'arm-2' })
    await waitFor(() => expect(requisicoes.has('arm-2')).toBe(true))
    expect(requisicoes.get('arm-1')?.sinal.aborted).toBe(true)

    await act(async () => {
      requisicoes.get('arm-2')?.pendente.resolver('dados novos')
      await requisicoes.get('arm-2')?.pendente.promise
    })
    expect(result.current.dados).toBe('dados novos')

    await act(async () => {
      requisicoes.get('arm-1')?.pendente.resolver('dados antigos')
      await requisicoes.get('arm-1')?.pendente.promise
    })
    expect(result.current.dados).toBe('dados novos')
  })

  it('recarrega os dados quando a ação é acionada', async () => {
    let chamadas = 0
    const carregar = async () => {
      chamadas += 1
      return chamadas === 1 ? 'primeiro' : 'segundo'
    }
    const { result } = renderHook(() => useCarregamento(carregar))

    await waitFor(() => expect(result.current.dados).toBe('primeiro'))
    act(() => result.current.recarregar())
    await waitFor(() => expect(result.current.dados).toBe('segundo'))
    expect(chamadas).toBe(2)
  })

  it('preserva os dados anteriores quando a recarga falha', async () => {
    let chamadas = 0
    const falha = new Error('falha na recarga')
    const carregar = async () => {
      chamadas += 1
      if (chamadas === 1) return 'dados anteriores'
      throw falha
    }
    const { result } = renderHook(() => useCarregamento(carregar))

    await waitFor(() => expect(result.current.dados).toBe('dados anteriores'))
    act(() => result.current.recarregar())
    await waitFor(() => expect(result.current.erro).toBe(falha))

    expect(result.current.dados).toBe('dados anteriores')
    expect(result.current.carregando).toBe(false)
  })
})
