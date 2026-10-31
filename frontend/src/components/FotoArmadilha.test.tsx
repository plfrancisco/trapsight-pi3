import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import FotoArmadilha from './FotoArmadilha'

describe('FotoArmadilha', () => {
  it('usa a foto real, com carregamento lazy, quando a API informa o tipo real', () => {
    render(
      <FotoArmadilha
        fotoTipo="real"
        fotoUrl="/api/armadilhas/arm-1/foto?v=123"
        identificador="ARM-001"
        modelo="StickFly K-45"
      />,
    )

    const imagem = screen.getByRole('img', { name: 'Foto da armadilha ARM-001' })
    expect(imagem).toHaveAttribute('src', 'http://localhost:8000/api/armadilhas/arm-1/foto?v=123')
    expect(imagem).toHaveAttribute('loading', 'lazy')
  })

  it('usa a foto padrão do modelo quando o tipo é padrão', () => {
    render(
      <FotoArmadilha
        fotoTipo="padrao"
        fotoUrl={null}
        identificador="ARM-001"
        modelo="StickFly K-45"
      />,
    )

    const imagem = screen.getByRole('img', { name: 'Foto padrão do modelo StickFly K-45' })
    expect(imagem).toHaveAttribute('loading', 'lazy')
    expect(imagem.getAttribute('src')).not.toContain('/api/')
  })

  it('volta à foto padrão do modelo quando a foto real não carrega', () => {
    render(
      <FotoArmadilha
        fotoTipo="real"
        fotoUrl="/api/armadilhas/arm-1/foto?v=123"
        identificador="ARM-001"
        modelo="StickFly K-45"
      />,
    )

    fireEvent.error(screen.getByRole('img', { name: 'Foto da armadilha ARM-001' }))

    expect(screen.queryByRole('img', { name: 'Foto da armadilha ARM-001' })).not.toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Foto padrão do modelo/ })).toBeVisible()
  })

  it('mostra um quadro de reserva quando nem o modelo tem foto', () => {
    render(
      <FotoArmadilha
        fotoTipo="padrao"
        fotoUrl={null}
        identificador="ARM-009"
        modelo="Modelo sem imagem"
      />,
    )

    expect(screen.getByRole('img', { name: 'Sem foto da armadilha ARM-009' })).toBeVisible()
  })
})
