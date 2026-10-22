import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import StatusBadge from './StatusBadge'

describe('StatusBadge', () => {
  it.each([
    ['ok', 'OK'],
    ['atencao', 'Atenção'],
    ['trocar', 'Trocar'],
  ] as const)('mostra o rótulo e a variante visual de %s', (status, rotulo) => {
    render(<StatusBadge status={status} />)

    const badge = screen.getByText(rotulo)
    expect(badge).toHaveClass('status-badge', `status-badge--${status}`)
    expect(badge.querySelector('[aria-hidden="true"]')).toHaveClass('status-badge__dot')
  })
})
