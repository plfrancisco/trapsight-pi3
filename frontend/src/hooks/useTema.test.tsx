import { act, renderHook } from '@testing-library/react'
import { expect, it } from 'vitest'
import { useTema } from './useTema'

it('sincroniza a cor da barra com os fundos dos dois temas', () => {
  localStorage.setItem('trapsight:tema', 'claro')
  const metas = ['(prefers-color-scheme: light)', '(prefers-color-scheme: dark)'].map(
    (media) => {
      const meta = document.createElement('meta')
      meta.name = 'theme-color'
      meta.media = media
      document.head.append(meta)
      return meta
    },
  )
  const { result, unmount } = renderHook(useTema)
  expect(metas.map((meta) => meta.content)).toEqual(['#f5f7f6', '#f5f7f6'])
  act(() => result.current.alternarTema())
  expect(metas.map((meta) => meta.content)).toEqual(['#0a1316', '#0a1316'])
  expect(document.documentElement.dataset.theme).toBe('escuro')
  unmount()
  metas.forEach((meta) => meta.remove())
  localStorage.clear()
  delete document.documentElement.dataset.theme
})

it('inicia no tema escuro quando não há preferência salva', () => {
  localStorage.clear()
  const { result, unmount } = renderHook(useTema)

  expect(result.current.tema).toBe('escuro')
  expect(document.documentElement.dataset.theme).toBe('escuro')

  unmount()
  localStorage.clear()
  delete document.documentElement.dataset.theme
})
