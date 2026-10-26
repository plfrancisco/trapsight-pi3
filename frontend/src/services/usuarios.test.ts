import { beforeEach, expect, it, vi } from 'vitest'
import { request } from './http'
import { createUsuario, listUsuarios, mensagemDeContas } from './usuarios'
import { ApiError } from './erros'

vi.mock('./http', () => ({ request: vi.fn() }))
beforeEach(() => vi.mocked(request).mockReset().mockResolvedValue({}))

it('envia somente os campos de criação permitidos', async () => {
  const dados = { email: 'a@exemplo.com', nome: 'Pessoa', senha: 'uma senha inicial segura', papel: 'gerente' }
  await createUsuario(dados)
  expect(request).toHaveBeenCalledWith('usuarios', {
    method: 'POST', body: { email: dados.email, nome: dados.nome, senha: dados.senha },
  })
})

it('consulta lista com cancelamento', async () => {
  const { signal } = new AbortController()
  await listUsuarios(signal)
  expect(request).toHaveBeenCalledWith('usuarios', { signal })
})

it.each(['EMAIL_JA_CADASTRADO', 'SENHA_FRACA', 'ACESSO_NEGADO', 'VALIDACAO_FALHOU'])('mapeia %s sem exibir texto do servidor', (codigo) => {
  expect(mensagemDeContas(new ApiError(codigo, 'segredo interno', 403))).not.toContain('segredo interno')
})
