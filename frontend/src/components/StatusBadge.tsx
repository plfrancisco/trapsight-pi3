import { rotuloStatus } from '../lib/formatacao'
import type { StatusAnalise } from '../services/tipos'

interface StatusBadgeProps {
  status: StatusAnalise
}

/** Exibe a cor e o rótulo textual do status para que a informação não dependa só da cor. */
export default function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span className={`status-badge status-badge--${status}`}>
      <span aria-hidden="true" className="status-badge__dot" />
      {rotuloStatus(status)}
    </span>
  )
}
