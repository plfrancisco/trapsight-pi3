import { request } from './http'
import type { SessaoAtual, TrocaSenhaSaida } from './tipos'

/** Autentica com e-mail e senha; o servidor define o cookie de sessão.
 * @param email E-mail da conta.
 * @param senha Senha da conta.
 * @param signal Cancelamento opcional da requisição.
 * @returns O usuário e o token CSRF da nova sessão.
 */
export function login(
  email: string,
  senha: string,
  signal?: AbortSignal,
): Promise<SessaoAtual> {
  return request<SessaoAtual>('auth/login', {
    method: 'POST',
    body: { email, senha },
    signal,
  })
}

/** Encerra a sessão no servidor (revogação real, não apenas limpeza do cookie). */
export function logout(signal?: AbortSignal): Promise<void> {
  return request<void>('auth/logout', { method: 'POST', signal })
}

/** Consulta a sessão atual; usada ao abrir o aplicativo para recuperar o estado. */
export function getSessao(signal?: AbortSignal): Promise<SessaoAtual> {
  return request<SessaoAtual>('auth/me', { signal })
}

/** Troca a própria senha; as demais sessões do usuário são encerradas.
 * @param senhaAtual Senha em uso.
 * @param senhaNova Nova senha, sujeita à política do servidor.
 * @param signal Cancelamento opcional da requisição.
 * @returns O token CSRF da sessão renovada.
 */
export function changeSenha(
  senhaAtual: string,
  senhaNova: string,
  signal?: AbortSignal,
): Promise<TrocaSenhaSaida> {
  return request<TrocaSenhaSaida>('auth/senha', {
    method: 'POST',
    body: { senha_atual: senhaAtual, senha_nova: senhaNova },
    signal,
  })
}
