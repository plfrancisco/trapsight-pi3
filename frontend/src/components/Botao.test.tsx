import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import Botao from './Botao'
import LinkBotao from './LinkBotao'

describe('Botao', () => {
  it.each([
    ['primario', 'bg-app-primary'],
    ['secundario', 'border-app-border'],
    ['discreto', 'text-app-muted'],
  ] as const)('aplica a variante %s com tamanho mínimo acessível', (variante, classe) => {
    render(<Botao variante={variante}>Ação</Botao>)

    const botao = screen.getByRole('button', { name: 'Ação' })
    expect(botao).toHaveClass(classe, 'min-h-11')
    expect(botao).toHaveClass('focus-visible:outline')
  })

  it('preserva o estado disabled nativo', () => {
    render(
      <Botao disabled variante="primario">
        Enviar
      </Botao>,
    )

    expect(screen.getByRole('button', { name: 'Enviar' })).toBeDisabled()
  })
})

describe('LinkBotao', () => {
  it('renderiza uma âncora com href e a variante solicitada', () => {
    render(
      <MemoryRouter>
        <LinkBotao to="/armadilhas/nova" variante="primario">
          Cadastrar
        </LinkBotao>
      </MemoryRouter>,
    )

    const link = screen.getByRole('link', { name: 'Cadastrar' })
    expect(link.tagName).toBe('A')
    expect(link).toHaveAttribute('href', '/armadilhas/nova')
    expect(link).toHaveClass('bg-app-primary', 'min-h-11')
  })
})
