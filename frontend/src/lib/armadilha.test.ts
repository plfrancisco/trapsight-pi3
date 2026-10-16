import { describe, expect, it } from 'vitest'
import { isArmadilhaAusente } from './armadilha'
import { ApiError } from '../services/erros'

describe('isArmadilhaAusente', () => {
  it('reconhece o código estável de armadilha não encontrada', () => {
    expect(
      isArmadilhaAusente(
        new ApiError('ARMADILHA_NAO_ENCONTRADA', 'Não encontrada.', 404),
      ),
    ).toBe(true)
  })

  it('reconhece validação UUID inválida para armadilha_id', () => {
    expect(
      isArmadilhaAusente(
        new ApiError('VALIDACAO_FALHOU', 'UUID inválido.', 422, {
          campos_invalidos: [
            { campo: 'armadilha_id', tipo: 'uuid_parsing' },
          ],
        }),
      ),
    ).toBe(true)
  })

  it('não classifica outros códigos ou erros de transporte como ausência', () => {
    expect(isArmadilhaAusente(new ApiError('ROTA_NAO_ENCONTRADA', 'Rota.', 404))).toBe(false)
    expect(isArmadilhaAusente(new ApiError('FALHA_DE_REDE', 'Rede.', 503))).toBe(false)
    expect(isArmadilhaAusente(new Error('Falha local.'))).toBe(false)
  })

  it('não confunde validação de outro campo com armadilha ausente', () => {
    expect(
      isArmadilhaAusente(
        new ApiError('VALIDACAO_FALHOU', 'Campo inválido.', 422, {
          campos_invalidos: [{ campo: 'identificador', tipo: 'string' }],
        }),
      ),
    ).toBe(false)
  })

  it('trata detalhes ausentes ou malformados com segurança', () => {
    expect(isArmadilhaAusente(new ApiError('VALIDACAO_FALHOU', 'Inválido.', 422))).toBe(false)
    expect(
      isArmadilhaAusente(
        new ApiError('VALIDACAO_FALHOU', 'Inválido.', 422, {
          campos_invalidos: { campo: 'armadilha_id' },
        }),
      ),
    ).toBe(false)
    expect(
      isArmadilhaAusente(
        new ApiError('VALIDACAO_FALHOU', 'Inválido.', 422, {
          campos_invalidos: [null, { campo: 42 }, 'armadilha_id'],
        }),
      ),
    ).toBe(false)
    expect(isArmadilhaAusente({ codigo: 'ARMADILHA_NAO_ENCONTRADA' })).toBe(false)
  })
})
