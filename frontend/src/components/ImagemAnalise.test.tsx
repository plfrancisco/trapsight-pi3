import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ImagemAnalise from './ImagemAnalise'

describe('ImagemAnalise', () => {
  it('por padrão mostra somente a foto original, sem legenda ou controle de máscara', () => {
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

  it('mostra a máscara, cai para a foto original se ela falhar e tenta de novo em outra análise', () => {
    const props = { descricao: 'da análise', height: 480, width: 640, imagemClassName: 'imagem' }
    const { rerender } = render(<ImagemAnalise analiseId="a1" variante="mascara" legenda {...props} />)
    const mascara = screen.getByRole('img', { name: 'Imagem com a máscara do modelo da análise' })
    expect(mascara).toHaveAttribute('src', 'http://localhost:8000/api/analises/a1/mascara')
    expect(screen.getByText('Área coberta da placa, marcada pelo modelo')).toBeVisible()

    fireEvent.error(mascara)
    expect(screen.getByRole('img', { name: 'Imagem original da análise' }))
      .toHaveAttribute('src', 'http://localhost:8000/api/analises/a1/imagem')
    expect(screen.queryByText('Área coberta da placa, marcada pelo modelo')).not.toBeInTheDocument()

    rerender(<ImagemAnalise analiseId="a2" variante="mascara" legenda {...props} />)
    expect(screen.getByRole('img', { name: 'Imagem com a máscara do modelo da análise' }))
      .toHaveAttribute('src', 'http://localhost:8000/api/analises/a2/mascara')
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
