import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import AvisoSemConexao from './AvisoSemConexao'

let descritorOnLine: PropertyDescriptor | undefined

afterEach(() => {
  if (descritorOnLine) {
    Object.defineProperty(navigator, 'onLine', descritorOnLine)
  } else {
    Reflect.deleteProperty(navigator, 'onLine')
  }
  descritorOnLine = undefined
})

it('mostra o aviso sem conexão e o remove quando a rede retorna', () => {
  descritorOnLine = Object.getOwnPropertyDescriptor(navigator, 'onLine')
  Object.defineProperty(navigator, 'onLine', { configurable: true, value: false })
  render(<AvisoSemConexao />)

  const aviso = screen.getByRole('status')
  expect(aviso).toHaveAttribute('aria-live', 'polite')
  expect(aviso).toHaveTextContent('Sem conexão. A análise precisa de internet.')

  Object.defineProperty(navigator, 'onLine', { configurable: true, value: true })
  fireEvent(window, new Event('online'))

  expect(screen.queryByRole('status')).not.toBeInTheDocument()
})

it('mostra o aviso quando a conexão cai durante a sessão', () => {
  descritorOnLine = Object.getOwnPropertyDescriptor(navigator, 'onLine')
  Object.defineProperty(navigator, 'onLine', { configurable: true, value: true })
  render(<AvisoSemConexao />)
  expect(screen.queryByRole('status')).not.toBeInTheDocument()

  Object.defineProperty(navigator, 'onLine', { configurable: true, value: false })
  fireEvent(window, new Event('offline'))

  expect(screen.getByRole('status')).toBeInTheDocument()
})
