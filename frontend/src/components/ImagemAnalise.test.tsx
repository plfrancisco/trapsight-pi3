import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import ImagemAnalise from './ImagemAnalise'

function renderizar(permitirAlternar = true, mostrarLegenda = true) {
  return render(
    <ImagemAnalise
      analiseId="analise-1"
      descricao="da análise de teste"
      height={480}
      imagemClassName="imagem"
      permitirAlternar={permitirAlternar}
      mostrarLegenda={mostrarLegenda}
      width={640}
    />,
  )
}

describe('ImagemAnalise', () => {
  it('mostra a máscara do modelo por padrão, com a legenda da cor', () => {
    renderizar()

    expect(
      screen.getByRole('img', { name: 'Identificação do modelo na imagem da análise de teste' }),
    ).toHaveAttribute('src', 'http://localhost:8000/api/analises/analise-1/mascara')
    expect(
      screen.getByText('Área marcada: cobertura por insetos identificada pelo modelo'),
    ).toBeVisible()
    expect(screen.getByRole('button', { name: 'Ver foto original' })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
  })

  it('alterna entre a máscara e a foto original', async () => {
    const usuario = userEvent.setup()
    renderizar()

    await usuario.click(screen.getByRole('button', { name: 'Ver foto original' }))

    expect(
      screen.getByRole('img', { name: 'Imagem original da análise de teste' }),
    ).toHaveAttribute('src', 'http://localhost:8000/api/analises/analise-1/imagem')
    expect(screen.queryByText(/Área marcada/)).not.toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Ver identificação do modelo' }),
    ).toHaveAttribute('aria-pressed', 'true')

    await usuario.click(screen.getByRole('button', { name: 'Ver identificação do modelo' }))

    expect(screen.getByRole('img')).toHaveAttribute(
      'src',
      'http://localhost:8000/api/analises/analise-1/mascara',
    )
  })

  it('cai para a foto original, sem botão nem legenda, quando a máscara não carrega', () => {
    renderizar()

    fireEvent.error(screen.getByRole('img'))

    expect(
      screen.getByRole('img', { name: 'Imagem original da análise de teste' }),
    ).toHaveAttribute('src', 'http://localhost:8000/api/analises/analise-1/imagem')
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.queryByText(/Área marcada/)).not.toBeInTheDocument()
  })

  it('não entra em laço quando a própria foto original falha', () => {
    renderizar()

    fireEvent.error(screen.getByRole('img'))
    fireEvent.error(screen.getByRole('img'))

    expect(screen.getByRole('img')).toHaveAttribute(
      'src',
      'http://localhost:8000/api/analises/analise-1/imagem',
    )
  })

  it('não mostra botão quando a alternância não é permitida', () => {
    renderizar(false)

    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.getByRole('img')).toHaveAttribute(
      'src',
      'http://localhost:8000/api/analises/analise-1/mascara',
    )
  })

  it('omite a legenda quando ela é desligada, como nas miniaturas', () => {
    renderizar(false, false)

    expect(screen.queryByText(/Área marcada/)).not.toBeInTheDocument()
  })
})
