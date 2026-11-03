import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { expect, it } from 'vitest'
import TituloPagina from './TituloPagina'

it.each([
  ['/', 'Dashboard'], ['/login', 'Entrar'],
  ['/armadilhas/nova', 'Nova armadilha'],
  ['/armadilhas/arm-1', 'Detalhe da armadilha'],
  ['/armadilhas/arm-1/editar', 'Editar armadilha'],
  ['/analises/nova', 'Nova análise'], ['/contas', 'Contas'],
  ['/conta/senha', 'Alterar senha'], ['/inexistente', 'Página não encontrada'],
])('identifica a rota %s', (rota, titulo) => {
  render(<MemoryRouter initialEntries={[rota]}><TituloPagina /></MemoryRouter>)
  expect(document.title).toBe(`${titulo} | TrapSight`)
})
