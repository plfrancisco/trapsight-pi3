import { ApiError } from './erros'
import { request } from './http'
import type { Conta, UsuarioEntrada } from './tipos'

/** Lista as contas autorizadas ao gerente, sem dados de senha. */
export function listUsuarios(signal?: AbortSignal): Promise<Conta[]> {
  return request<Conta[]>('usuarios', { signal })
}

/** Cria um operador; a API decide papel e estado da conta. */
export function createUsuario(dados: UsuarioEntrada): Promise<Conta> {
  return request<Conta>('usuarios', {
    method: 'POST',
    body: { email: dados.email, nome: dados.nome, senha: dados.senha },
  })
}

/** Exclui uma conta de operador; a API valida gerente, CSRF e alvo permitido. */
export function deleteUsuario(usuarioId: string): Promise<void> {
  return request<void>(`usuarios/${encodeURIComponent(usuarioId)}`, {
    method: 'DELETE',
  })
}

/** Traduz falhas de gestão por código estável sem exibir detalhes internos. */
export function mensagemDeContas(falha: unknown): string {
  if (falha instanceof ApiError) {
    switch (falha.codigo) {
      case 'EMAIL_JA_CADASTRADO':
        return 'Já existe uma conta com este e-mail.'
      case 'CONTA_NAO_ENCONTRADA':
        return 'Esta conta já foi removida ou não existe.'
      case 'SENHA_FRACA':
        return 'A senha inicial não atende à política. Use ao menos 8 caracteres, com letras e números, e evite senhas comuns ou ligadas à conta.'
      case 'ACESSO_NEGADO':
        return 'Acesso restrito ao gerente.'
      case 'VALIDACAO_FALHOU':
        return 'Confira o nome, o e-mail e a senha informados.'
      case 'CSRF_INVALIDO':
        return 'Não foi possível confirmar a operação. Recarregue a página.'
    }
  }
  return 'Não foi possível carregar ou salvar as contas. Tente novamente.'
}
