import { act, renderHook } from '@testing-library/react'
import { expect, it } from 'vitest'
import { useTema } from './useTema'

it('sincroniza a cor da barra com os fundos dos dois temas', () => {
  localStorage.setItem('trapsight:tema', 'claro')
  const meta = document.createElement('meta')
  meta.name = 'theme-color'
  document.head.append(meta)
  const { result, unmount } = renderHook(useTema)
  expect(meta.content).toBe('#f5f7f6')
  act(() => result.current.alternarTema())
  expect(meta.content).toBe('#0a1316')
  expect(document.documentElement.dataset.theme).toBe('escuro')
  unmount()
  meta.remove()
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
