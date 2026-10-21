import { createContext } from 'react'
import type { Usuario } from '../services/tipos'

/** Situação da autenticação do aplicativo. */
export type EstadoAuth = 'carregando' | 'autenticado' | 'anonimo' | 'erro'

/** Como a sessão terminou: expirou no servidor ou o usuário saiu. */
export type MotivoSaida = 'expirou' | 'saiu' | null

/** Valor compartilhado pelo provedor de autenticação. */
export interface AuthContextoValor {
  /** Falso quando a exigência de login está desligada (chave temporária). */
  ativa: boolean
  estado: EstadoAuth
  usuario: Usuario | null
  motivoSaida: MotivoSaida
  login: (email: string, senha: string) => Promise<void>
  logout: () => Promise<void>
  changeSenha: (senhaAtual: string, senhaNova: string) => Promise<void>
  recarregarSessao: () => void
}

export const AuthContexto = createContext<AuthContextoValor | null>(null)
