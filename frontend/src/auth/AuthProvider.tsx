import {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useState,
  type ReactNode,
} from 'react'
import { AUTENTICACAO_ATIVA } from '../config'
import * as api from '../services/auth'
import { ApiError } from '../services/erros'
import {
  assinarSessaoExpirada,
  definirCsrf,
  limparCsrf,
} from '../services/sessao'
import type { Usuario } from '../services/tipos'
import {
  AuthContexto,
  type AuthContextoValor,
  type EstadoAuth,
  type MotivoSaida,
} from './contexto'

interface SituacaoAuth {
  estado: EstadoAuth
  usuario: Usuario | null
  motivoSaida: MotivoSaida
}

type Acao =
  | { tipo: 'carregando' }
  | { tipo: 'sessao'; usuario: Usuario }
  | { tipo: 'anonimo' }
  | { tipo: 'erro' }
  | { tipo: 'saiu' }
  | { tipo: 'expirou' }

function reduzir(situacao: SituacaoAuth, acao: Acao): SituacaoAuth {
  switch (acao.tipo) {
    case 'carregando':
      return { ...situacao, estado: 'carregando' }
    case 'sessao':
      return { estado: 'autenticado', usuario: acao.usuario, motivoSaida: null }
    case 'anonimo':
      return { ...situacao, estado: 'anonimo', usuario: null }
    case 'erro':
      return { ...situacao, estado: 'erro' }
    case 'saiu':
      return { estado: 'anonimo', usuario: null, motivoSaida: 'saiu' }
    case 'expirou':
      // Só importa se havia sessão: no início, um 401 é apenas "ainda não entrou".
      return situacao.estado === 'autenticado'
        ? { estado: 'anonimo', usuario: null, motivoSaida: 'expirou' }
        : situacao
  }
}

interface AuthProviderProps {
  children: ReactNode
  /** Substitui a chave global de autenticação (usado em testes). */
  ativa?: boolean
}

/** Mantém o estado de autenticação e o disponibiliza ao aplicativo.
 * @param props Conteúdo e, opcionalmente, o liga/desliga da autenticação.
 * @returns O provedor do contexto de autenticação.
 */
export default function AuthProvider({
  children,
  ativa = AUTENTICACAO_ATIVA,
}: AuthProviderProps) {
  const [situacao, dispatch] = useReducer(
    reduzir,
    ativa
      ? { estado: 'carregando', usuario: null, motivoSaida: null }
      : { estado: 'autenticado', usuario: null, motivoSaida: null },
  )
  const [tentativa, setTentativa] = useState(0)

  // Recupera a sessão ao abrir o aplicativo (e a cada nova tentativa).
  useEffect(() => {
    if (!ativa) return
    const controlador = new AbortController()

    api
      .getSessao(controlador.signal)
      .then((sessao) => {
        definirCsrf(sessao.csrf_token)
        dispatch({ tipo: 'sessao', usuario: sessao.usuario })
      })
      .catch((falha: unknown) => {
        if (controlador.signal.aborted) return
        limparCsrf()
        dispatch(
          falha instanceof ApiError && falha.status === 401
            ? { tipo: 'anonimo' }
            : { tipo: 'erro' },
        )
      })

    return () => controlador.abort()
  }, [ativa, tentativa])

  // Qualquer resposta "NAO_AUTENTICADO" da API encerra a sessão local.
  useEffect(
    () =>
      assinarSessaoExpirada(() => {
        limparCsrf()
        dispatch({ tipo: 'expirou' })
      }),
    [],
  )

  const login = useCallback(async (email: string, senha: string) => {
    const sessao = await api.login(email, senha)
    definirCsrf(sessao.csrf_token)
    dispatch({ tipo: 'sessao', usuario: sessao.usuario })
  }, [])

  const logout = useCallback(async () => {
    try {
      await api.logout()
    } catch (falha: unknown) {
      // Se a sessão já não existia no servidor, sair está concluído.
      if (!(falha instanceof ApiError && falha.status === 401)) throw falha
    }
    limparCsrf()
    dispatch({ tipo: 'saiu' })
  }, [])

  const changeSenha = useCallback(async (senhaAtual: string, senhaNova: string) => {
    const renovada = await api.changeSenha(senhaAtual, senhaNova)
    definirCsrf(renovada.csrf_token)
  }, [])

  const recarregarSessao = useCallback(() => {
    dispatch({ tipo: 'carregando' })
    setTentativa((valor) => valor + 1)
  }, [])

  const valor = useMemo<AuthContextoValor>(
    () => ({
      ativa,
      estado: situacao.estado,
      usuario: situacao.usuario,
      motivoSaida: situacao.motivoSaida,
      login,
      logout,
      changeSenha,
      recarregarSessao,
    }),
    [ativa, situacao, login, logout, changeSenha, recarregarSessao],
  )

  return <AuthContexto.Provider value={valor}>{children}</AuthContexto.Provider>
}
