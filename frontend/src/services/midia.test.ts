import { describe, expect, it } from 'vitest'
import { API_URL } from '../config'
import {
  urlAbsoluta,
  urlImagemAnalise,
} from './midia'

describe('URLs de mídia', () => {
  it('monta as URLs da imagem original sem fazer requisição', () => {
    const origem = new URL(API_URL).origin
    expect(urlImagemAnalise('analise-1')).toBe(
      origem + new URL(API_URL).pathname.replace(/\/+$/, '') + '/analises/analise-1/imagem',
    )
  })

  it('combina um caminho relativo com a origem pública da API', () => {
    expect(urlAbsoluta('/api/analises/analise-1/imagem')).toBe(
      new URL('/api/analises/analise-1/imagem', new URL(API_URL).origin).toString(),
    )
  })

  it('rejeita caminhos de mídia apontando para outra origem', () => {
    expect(() => urlAbsoluta('https://exemplo.invalid/imagem')).toThrow(TypeError)
  })
})
