import { describe, expect, it } from 'vitest'
import {
  indiceQuadroMaisProximo,
  instanteDoQuadro,
  mapearArrastoParaIndice,
} from './marcadorGrafico'

describe('funções do marcador do gráfico', () => {
  it('encontra o quadro temporal mais próximo em listas de um ou vários itens', () => {
    expect(indiceQuadroMaisProximo([1000], 1200)).toBe(0)
    expect(indiceQuadroMaisProximo([1000, 3000, 5000], 3900)).toBe(1)
    expect(indiceQuadroMaisProximo([1000, 3000], 2000)).toBe(0)
    expect(indiceQuadroMaisProximo([], 2000)).toBe(-1)
  })

  it('mapeia um arrasto para a análise mais próxima', () => {
    expect(mapearArrastoParaIndice([1000, 3000, 5000], 4600)).toBe(2)
  })

  it('obtém o instante de um quadro sem aceitar índices inexistentes', () => {
    expect(instanteDoQuadro([1000, 3000], 1)).toBe(3000)
    expect(instanteDoQuadro([1000], 0)).toBe(1000)
    expect(instanteDoQuadro([], 0)).toBeNull()
    expect(instanteDoQuadro([1000], 2)).toBeNull()
  })
})
