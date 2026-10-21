import { useContext } from 'react'
import { AuthContexto, type AuthContextoValor } from './contexto'

/**
 * Acessa o estado de autenticação.
 *
 * @returns O valor do provedor de autenticação.
 * @throws Error quando usado fora de AuthProvider.
 */
export function useAuth(): AuthContextoValor {
  const valor = useContext(AuthContexto)
  if (!valor) throw new Error('useAuth precisa estar dentro de AuthProvider.')
  return valor
}
