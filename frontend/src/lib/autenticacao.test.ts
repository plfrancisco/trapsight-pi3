import { describe, expect, it } from 'vitest'
import { ApiError } from '../services/erros'
import {
  SENHA_TAMANHO_MAXIMO,
  SENHA_TAMANHO_MINIMO,
  mensagemDeLogin,
  mensagemDeTrocaSenha,
  validateNovaSenha,
} from './autenticacao'

const erro = (codigo: string, mensagem = 'texto do servidor', status = 401) =>
  new ApiError(codigo, mensagem, status)

describe('mensagemDeLogin', () => {
  it('usa uma mensagem única para credenciais inválidas', () => {
    expect(mensagemDeLogin(erro('CREDENCIAIS_INVALIDAS'))).toBe('E-mail ou senha inválidos.')
  })

  it('orienta a esperar quando o limite de tentativas é atingido', () => {
    expect(mensagemDeLogin(erro('LIMITE_TENTATIVAS', 'x', 429))).toMatch(/Aguarde/)
  })

  it('pede para recarregar quando a proteção CSRF recusa', () => {
    expect(mensagemDeLogin(erro('CSRF_INVALIDO', 'x', 403))).toMatch(/Recarregue/)
  })

  it.each(['FALHA_DE_REDE', 'TEMPO_ESGOTADO'])('trata %s como problema de conexão', (codigo) => {
    expect(mensagemDeLogin(erro(codigo, 'x', 0))).toMatch(/conectar/)
  })

  it('nunca exibe o texto enviado pelo servidor, mesmo para códigos desconhecidos', () => {
    const textoDoServidor = 'A conta bloqueada@exemplo.com está bloqueada'
    expect(mensagemDeLogin(erro('CODIGO_NOVO', textoDoServidor))).not.toContain(textoDoServidor)
    expect(mensagemDeLogin(erro('CREDENCIAIS_INVALIDAS', textoDoServidor))).not.toContain(
      textoDoServidor,
    )
  })

  it('usa uma mensagem genérica para falhas que não são da API', () => {
    expect(mensagemDeLogin(new Error('boom'))).toBe('Não foi possível entrar. Tente novamente.')
    expect(mensagemDeLogin('texto')).toBe('Não foi possível entrar. Tente novamente.')
  })
})

describe('mensagemDeTrocaSenha', () => {
  it('diferencia a senha atual errada', () => {
    expect(mensagemDeTrocaSenha(erro('CREDENCIAIS_INVALIDAS'))).toBe('A senha atual está incorreta.')
  })

  it('explica a política quando a senha é fraca', () => {
    const texto = mensagemDeTrocaSenha(erro('SENHA_FRACA', 'x', 422))
    expect(texto).toContain(String(SENHA_TAMANHO_MINIMO))
  })

  it('não repete a senha nem o texto do servidor', () => {
    expect(mensagemDeTrocaSenha(erro('SENHA_FRACA', 'Senha fraca: segredo123', 422))).not.toContain(
      'segredo123',
    )
  })

  it('usa mensagem genérica para o resto', () => {
    expect(mensagemDeTrocaSenha(erro('OUTRO', 'x', 500))).toBe(
      'Não foi possível alterar a senha. Tente novamente.',
    )
  })
})

describe('validateNovaSenha', () => {
  const longa = 'a'.repeat(SENHA_TAMANHO_MINIMO)

  it('aceita o tamanho mínimo e o máximo, sem exigir composição', () => {
    expect(validateNovaSenha(longa, longa)).toBeNull()
    const maxima = 'b'.repeat(SENHA_TAMANHO_MAXIMO)
    expect(validateNovaSenha(maxima, maxima)).toBeNull()
  })

  it('recusa senha abaixo do mínimo', () => {
    const curta = 'a'.repeat(SENHA_TAMANHO_MINIMO - 1)
    expect(validateNovaSenha(curta, curta)).toMatch(/pelo menos/)
  })

  it('recusa senha acima do máximo', () => {
    const grande = 'a'.repeat(SENHA_TAMANHO_MAXIMO + 1)
    expect(validateNovaSenha(grande, grande)).toMatch(/no máximo/)
  })

  it('exige que a confirmação coincida', () => {
    expect(validateNovaSenha(longa, longa + 'x')).toMatch(/confirmação/)
  })

  it('conta pontos de código, não unidades UTF-16 (emoji vale um caractere)', () => {
    const emojis = '🪰'.repeat(SENHA_TAMANHO_MINIMO)
    expect(emojis.length).toBeGreaterThan(SENHA_TAMANHO_MINIMO)
    expect(validateNovaSenha(emojis, emojis)).toBeNull()
    const quatorze = '🪰'.repeat(SENHA_TAMANHO_MINIMO - 1)
    expect(validateNovaSenha(quatorze, quatorze)).toMatch(/pelo menos/)
  })
})
