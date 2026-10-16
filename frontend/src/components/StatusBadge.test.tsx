import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import StatusBadge from './StatusBadge'

describe('StatusBadge', () => {
  it.each([
    ['ok', 'OK', '#16A34A'],
    ['atencao', 'Atenção', '#F59E0B'],
    ['trocar', 'Trocar', '#DC2626'],
  ] as const)('mostra o rótulo e a cor de %s', (status, rotulo, cor) => {
    render(<StatusBadge status={status} />)

    const badge = screen.getByText(rotulo)
    expect(badge).toHaveClass('bg-white', 'text-slate-950', `border-[${cor}]`)
    expect(badge.querySelector('[aria-hidden="true"]')).toHaveClass(`bg-[${cor}]`)
  })
})
