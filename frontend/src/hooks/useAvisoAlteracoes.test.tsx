import { useRef } from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useAvisoAlteracoes } from './useAvisoAlteracoes'

function Formulario() {
  const ref = useRef<HTMLFormElement>(null)
  const salvo = useAvisoAlteracoes(ref, true)
  return <form ref={ref}>
    <input aria-label="Localização" defaultValue="Cozinha" name="localizacao" />
    <input aria-label="Foto" name="foto" type="file" />
    <a href="/outra">Cancelar</a>
    <button onClick={salvo} type="button">Salvar</button>
  </form>
}

afterEach(() => vi.restoreAllMocks())

function fechar() {
  const evento = new Event('beforeunload', { cancelable: true })
  window.dispatchEvent(evento)
  return evento.defaultPrevented
}

describe('useAvisoAlteracoes', () => {
  it('avisa ao fechar com alterações, mas não após desfazer a edição', () => {
    render(<Formulario />)
    expect(fechar()).toBe(false)
    fireEvent.change(screen.getByLabelText('Localização'), { target: { value: 'Depósito' } })
    expect(fechar()).toBe(true)
    fireEvent.change(screen.getByLabelText('Localização'), { target: { value: 'Cozinha' } })
    expect(fechar()).toBe(false)
  })

  it('impede seguir links quando a pessoa decide continuar editando', () => {
    const confirmar = vi.spyOn(window, 'confirm').mockReturnValue(false)
    render(<Formulario />)
    fireEvent.change(screen.getByLabelText('Localização'), { target: { value: 'Depósito' } })
    expect(fireEvent.click(screen.getByText('Cancelar'))).toBe(false)
    expect(confirmar).toHaveBeenCalledWith('Há alterações não salvas. Sair e descartá-las?')
  })

  it('libera a navegação depois de salvar e remove os eventos ao desmontar', () => {
    const { unmount } = render(<Formulario />)
    fireEvent.change(screen.getByLabelText('Localização'), { target: { value: 'Depósito' } })
    fireEvent.click(screen.getByText('Salvar'))
    expect(fechar()).toBe(false)
    unmount()
    expect(fechar()).toBe(false)
  })
})
