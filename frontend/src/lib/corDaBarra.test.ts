import { afterEach, expect, it } from 'vitest'
import { atualizarCorDaBarra } from './corDaBarra'

const metas = ['(prefers-color-scheme: light)', '(prefers-color-scheme: dark)'].map(
  (media) => {
    const meta = document.createElement('meta')
    meta.name = 'theme-color'
    meta.media = media
    document.head.append(meta)
    return meta
  },
)

afterEach(() => metas.forEach((meta) => meta.remove()))

it('atualiza todas as meta tags para a cor do tema claro ou escuro', () => {
  atualizarCorDaBarra('claro')
  expect(metas.map((meta) => meta.content)).toEqual(['#f5f7f6', '#f5f7f6'])

  atualizarCorDaBarra('escuro')
  expect(metas.map((meta) => meta.content)).toEqual(['#0a1316', '#0a1316'])
})
