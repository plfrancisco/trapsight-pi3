import { rotuloStatus } from '../lib/formatacao'
import type { StatusAnalise } from '../services/tipos'

const CLASSES_BORDA: Record<StatusAnalise, string> = {
  ok: 'border-[#16A34A]',
  atencao: 'border-[#F59E0B]',
  trocar: 'border-[#DC2626]',
}

const CLASSES_PONTO: Record<StatusAnalise, string> = {
  ok: 'bg-[#16A34A]',
  atencao: 'bg-[#F59E0B]',
  trocar: 'bg-[#DC2626]',
}

interface StatusBadgeProps {
  status: StatusAnalise
}

/** Exibe a cor e o rótulo textual do status para que a informação não dependa só da cor. */
export default function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex min-h-8 items-center gap-2 rounded-full border bg-white px-3 py-1 text-sm font-semibold text-slate-950 ${CLASSES_BORDA[status]}`}
    >
      <span aria-hidden="true" className={`size-2.5 rounded-full ${CLASSES_PONTO[status]}`} />
      {rotuloStatus(status)}
    </span>
  )
}
