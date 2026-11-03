import { act, renderHook } from '@testing-library/react'
import { expect, it } from 'vitest'
import { useTema } from './useTema'

it('sincroniza a cor da barra com os fundos dos dois temas', () => {
  localStorage.setItem('trapsight:tema', 'claro')
  const meta = document.createElement('meta')
  meta.name = 'theme-color'
  document.head.append(meta)
  const { result, unmount } = renderHook(useTema)
  expect(meta.content).toBe('#f6f7f5')
  act(() => result.current.alternarTema())
  expect(meta.content).toBe('#111416')
  expect(document.documentElement.dataset.theme).toBe('escuro')
  unmount()
  meta.remove()
  localStorage.clear()
  delete document.documentElement.dataset.theme
})
