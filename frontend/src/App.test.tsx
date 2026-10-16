import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import { Rotas } from './App'

const montarRota = (caminho: string) =>
  render(
    <MemoryRouter initialEntries={[caminho]}>
      <Rotas />
    </MemoryRouter>,
  )

describe('rotas e navegação', () => {
  it.each([
    ['/', 'Dashboard'],
    ['/armadilhas/arm-1', 'Detalhe da armadilha'],
    ['/analises/nova', 'Nova análise'],
    ['/armadilhas/nova', 'Nova armadilha'],
    ['/armadilhas/arm-1/editar', 'Editar armadilha'],
  ])('renderiza o título correto em %s', (caminho, titulo) => {
    montarRota(caminho)
    expect(screen.getByRole('heading', { name: titulo, level: 1 })).toBeVisible()
  })

  it('renderiza a página 404 para endereços desconhecidos', () => {
    montarRota('/rota-inexistente')

    expect(
      screen.getByRole('heading', { name: 'Página não encontrada', level: 1 }),
    ).toBeVisible()
  })

  it('resolve o cadastro antes do parâmetro de detalhe e conserva a rota de edição', () => {
    const cadastro = montarRota('/armadilhas/nova')
    expect(screen.getByRole('heading', { name: 'Nova armadilha' })).toBeVisible()

    cadastro.unmount()
    montarRota('/armadilhas/arm-1/editar')
    expect(screen.getByRole('heading', { name: 'Editar armadilha' })).toBeVisible()
  })

  it('apresenta os links principais e acompanha a rota ativa', async () => {
    const usuario = userEvent.setup()
    montarRota('/')

    expect(screen.getByRole('navigation', { name: 'Navegação principal' })).toBeVisible()
    expect(screen.getByRole('link', { name: 'Dashboard' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(screen.getByRole('link', { name: 'Nova análise' })).toBeVisible()
    expect(screen.getByRole('link', { name: 'Nova armadilha' })).toBeVisible()

    await usuario.click(screen.getByRole('link', { name: 'Nova análise' }))

    expect(screen.getByRole('heading', { name: 'Nova análise' })).toBeVisible()
    expect(screen.getByRole('link', { name: 'Nova análise' })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  it('oferece um link para pular diretamente ao conteúdo principal', () => {
    montarRota('/')

    expect(screen.getByRole('link', { name: 'Pular para o conteúdo' })).toHaveAttribute(
      'href',
      '#conteudo-principal',
    )
    expect(document.getElementById('conteudo-principal')).toBeInTheDocument()
  })
})
