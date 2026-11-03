import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ImagemAnalise from './ImagemAnalise'

describe('ImagemAnalise', () => {
  it('mostra somente a foto original, sem legenda ou controle de máscara', () => {
    render(<ImagemAnalise analiseId="analise-1" descricao="da análise de teste"
      height={480} width={640} imagemClassName="imagem" />)
    const imagem = screen.getByRole('img', { name: 'Imagem original da análise de teste' })
    expect(imagem).toHaveAttribute('src', 'http://localhost:8000/api/analises/analise-1/imagem')
    expect(imagem).toHaveAttribute('width', '640')
    expect(imagem).toHaveAttribute('height', '480')
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.queryByText(/Área marcada/)).not.toBeInTheDocument()
    fireEvent.error(imagem)
    expect(imagem).toHaveAttribute('src', 'http://localhost:8000/api/analises/analise-1/imagem')
  })

  it('atualiza a foto ao selecionar outra análise', () => {
    const { rerender } = render(<ImagemAnalise analiseId="primeira" descricao="primeira"
      height={480} width={640} imagemClassName="imagem" moldura="moldura" />)
    rerender(<ImagemAnalise analiseId="segunda" descricao="segunda"
      height={480} width={640} imagemClassName="imagem" moldura="moldura" />)
    expect(screen.getByRole('img', { name: 'Imagem original segunda' }))
      .toHaveAttribute('src', 'http://localhost:8000/api/analises/segunda/imagem')
  })
})
