import { ApiError } from '../services/erros'

/** Tamanho mínimo da senha (login.md, 5.2): a senha é o único fator. */
export const SENHA_TAMANHO_MINIMO = 15
/** Tamanho máximo aceito pelo servidor. */
export const SENHA_TAMANHO_MAXIMO = 128

const MENSAGEM_REDE = 'Não foi possível conectar. Verifique a conexão e tente novamente.'

function codigoDe(falha: unknown): string | null {
  return falha instanceof ApiError ? falha.codigo : null
}

function motivoDe(falha: unknown): string | null {
  if (!(falha instanceof ApiError)) return null
  const motivo = falha.detalhes?.motivo
  return typeof motivo === 'string' ? motivo : null
}

/**
 * Traduz uma falha de login em texto para o usuário, decidindo SEMPRE pelo código.
 * O texto vindo do servidor nunca é exibido: a mensagem única impede descobrir se
 * a conta existe, está bloqueada ou foi desativada.
 *
 * @param falha Erro lançado pela chamada de login.
 * @returns Mensagem em português para a tela de login.
 */
export function mensagemDeLogin(falha: unknown): string {
  switch (codigoDe(falha)) {
    case 'CREDENCIAIS_INVALIDAS':
      return 'E-mail ou senha inválidos.'
    case 'LIMITE_TENTATIVAS':
      return 'Muitas tentativas. Aguarde alguns minutos e tente novamente.'
    case 'CSRF_INVALIDO':
      return 'Não foi possível entrar. Recarregue a página e tente novamente.'
    case 'FALHA_DE_REDE':
    case 'TEMPO_ESGOTADO':
      return MENSAGEM_REDE
    default:
      return 'Não foi possível entrar. Tente novamente.'
  }
}

/**
 * Traduz uma falha da troca de senha em texto para o usuário, pelo código do erro.
 *
 * @param falha Erro lançado pela chamada de troca de senha.
 * @returns Mensagem em português para a tela de alterar senha.
 */
export function mensagemDeTrocaSenha(falha: unknown): string {
  switch (codigoDe(falha)) {
    case 'CREDENCIAIS_INVALIDAS':
      return 'A senha atual está incorreta.'
    case 'SENHA_FRACA':
      if (motivoDe(falha) === 'igual_atual') {
        return 'A nova senha precisa ser diferente da senha atual.'
      }
      return `A nova senha não atende à política: use ao menos ${SENHA_TAMANHO_MINIMO} caracteres e evite senhas comuns ou ligadas ao seu e-mail.`
    case 'FALHA_DE_REDE':
    case 'TEMPO_ESGOTADO':
      return MENSAGEM_REDE
    default:
      return 'Não foi possível alterar a senha. Tente novamente.'
  }
}

/**
 * Valida a nova senha no cliente antes do envio. O servidor continua sendo a
 * autoridade: aqui só se evitam erros óbvios, sem regra de composição.
 *
 * @param nova Nova senha digitada.
 * @param confirmacao Confirmação digitada.
 * @returns Mensagem de erro ou null quando pode enviar.
 */
export function validateNovaSenha(nova: string, confirmacao: string): string | null {
  const tamanho = [...nova].length // cada ponto de código conta como um caractere
  if (tamanho < SENHA_TAMANHO_MINIMO) {
    return `A nova senha precisa ter pelo menos ${SENHA_TAMANHO_MINIMO} caracteres.`
  }
  if (tamanho > SENHA_TAMANHO_MAXIMO) {
    return `A nova senha pode ter no máximo ${SENHA_TAMANHO_MAXIMO} caracteres.`
  }
  if (nova !== confirmacao) return 'A confirmação não confere com a nova senha.'
  return null
}
