import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import ControlesTimelapse from './ControlesTimelapse'

describe('ControlesTimelapse', () => {
  it('rotula o escopo, a reprodução, o quadro e a velocidade', () => {
    render(
      <ControlesTimelapse
        escopo="refil_ativo"
        indiceQuadro={0}
        quantidade={3}
        reproduzindo={false}
        velocidadeMs={500}
        onChangeEscopo={vi.fn()}
        onChangeQuadro={vi.fn()}
        onChangeVelocidade={vi.fn()}
        onTogglePlayback={vi.fn()}
      />,
    )

    expect(screen.getByRole('group', { name: 'Escopo temporal' })).toBeVisible()
    expect(screen.getByRole('radio', { name: 'Refil ativo' })).toBeChecked()
    expect(screen.getByRole('radio', { name: 'Histórico completo' })).not.toBeChecked()
    expect(screen.getByRole('button', { name: 'Reproduzir' })).toBeVisible()
    expect(screen.getByRole('slider', { name: 'Quadro atual: 1 de 3' })).toBeVisible()
    expect(screen.getByRole('slider', { name: 'Velocidade: 500 ms por quadro' })).toHaveValue('500')
  })

  it('encaminha seleção manual do quadro, escopo e velocidade', () => {
    const onChangeEscopo = vi.fn()
    const onChangeQuadro = vi.fn()
    const onChangeVelocidade = vi.fn()
    const onTogglePlayback = vi.fn()
    render(
      <ControlesTimelapse
        escopo="refil_ativo"
        indiceQuadro={0}
        quantidade={3}
        reproduzindo={false}
        velocidadeMs={500}
        onChangeEscopo={onChangeEscopo}
        onChangeQuadro={onChangeQuadro}
        onChangeVelocidade={onChangeVelocidade}
        onTogglePlayback={onTogglePlayback}
      />,
    )

    fireEvent.click(screen.getByRole('radio', { name: 'Histórico completo' }))
    fireEvent.change(screen.getByRole('slider', { name: 'Quadro atual: 1 de 3' }), {
      target: { value: '2' },
    })
    fireEvent.change(screen.getByRole('slider', { name: 'Velocidade: 500 ms por quadro' }), {
      target: { value: '700' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Reproduzir' }))

    expect(onChangeEscopo).toHaveBeenCalledWith('completo')
    expect(onChangeQuadro).toHaveBeenCalledWith(2)
    expect(onChangeVelocidade).toHaveBeenCalledWith(700)
    expect(onTogglePlayback).toHaveBeenCalledOnce()
  })

  it('oculta reprodução e sliders com menos de dois quadros', () => {
    render(
      <ControlesTimelapse
        escopo="refil_ativo"
        indiceQuadro={0}
        quantidade={1}
        reproduzindo={false}
        velocidadeMs={500}
        onChangeEscopo={vi.fn()}
        onChangeQuadro={vi.fn()}
        onChangeVelocidade={vi.fn()}
        onTogglePlayback={vi.fn()}
      />,
    )

    expect(screen.getByRole('group', { name: 'Escopo temporal' })).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Reproduzir' })).not.toBeInTheDocument()
    expect(screen.queryByRole('slider')).not.toBeInTheDocument()
  })
})
