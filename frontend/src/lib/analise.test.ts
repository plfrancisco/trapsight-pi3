import { describe, expect, it } from 'vitest'
import { buildMensagemErroAnalise, validateArquivoAnalise } from './analise'

describe('validateArquivoAnalise', () => {
  it('aceita JPEG e PNG com tipo e extensão correspondentes até 10 MB', () => {
    expect(
      validateArquivoAnalise({
        name: 'placa.JPG',
        type: 'image/jpeg',
        size: 10 * 1024 * 1024,
      }),
    ).toBeNull()
    expect(
      validateArquivoAnalise({
        name: 'placa.png',
        type: 'image/png',
        size: 1024,
      }),
    ).toBeNull()
  })

  it('rejeita extensão e tipo divergentes nos dois sentidos', () => {
    const mensagem = 'Selecione um arquivo JPEG (.jpg ou .jpeg) ou PNG (.png).'
    expect(
      validateArquivoAnalise({
        name: 'placa.png',
        type: 'image/jpeg',
        size: 1024,
      }),
    ).toBe(mensagem)
    expect(
      validateArquivoAnalise({
        name: 'placa.jpg',
        type: 'image/png',
        size: 1024,
      }),
    ).toBe(mensagem)
  })

  it('rejeita arquivos acima de 10 MB', () => {
    expect(
      validateArquivoAnalise({
        name: 'placa.jpg',
        type: 'image/jpeg',
        size: 10 * 1024 * 1024 + 1,
      }),
    ).toBe('O arquivo deve ter no máximo 10 MB.')
  })
})

describe('buildMensagemErroAnalise', () => {
  it.each([
    ['ARQUIVO_MUITO_GRANDE', 'A imagem excede o limite de 10 MB.'],
    ['FORMATO_NAO_SUPORTADO', 'Envie uma imagem JPEG ou PNG.'],
    [
      'RESOLUCAO_INSUFICIENTE',
      'A imagem precisa ter pelo menos 512 px no maior lado.',
    ],
    [
      'REFIL_ATIVO_INEXISTENTE',
      'Esta armadilha não tem refil ativo. Registre um refil antes de enviar a análise.',
    ],
    [
      'PLACA_NAO_DETECTADA',
      'Não foi possível detectar a superfície adesiva na imagem.',
    ],
    [
      'FALHA_INFERENCIA',
      'A análise não pôde ser concluída. Tente novamente mais tarde.',
    ],
    [
      'FALHA_DE_REDE',
      'Não foi possível conectar à API. Verifique a conexão e tente novamente.',
    ],
    ['TEMPO_ESGOTADO', 'A análise excedeu o tempo limite. Tente novamente.'],
  ])('mapeia %s para uma mensagem em português', (codigo, texto) => {
    expect(buildMensagemErroAnalise(codigo, 'texto genérico da API')).toBe(texto)
  })

  it('preserva a mensagem da API para códigos desconhecidos', () => {
    expect(
      buildMensagemErroAnalise('CODIGO_FUTURO', 'Mensagem original da API'),
    ).toBe('Mensagem original da API')
  })
})
