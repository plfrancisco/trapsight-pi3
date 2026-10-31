import { formatData, formatDiasAteSaturar, formatPercentual } from '../lib/formatacao'
import type { RefilAtivo, StatusAnalise } from '../services/tipos'
import StatusBadge from './StatusBadge'

interface ResumoRefilProps {
  refil: RefilAtivo | null
  percentualAtual: number | null
  status: StatusAnalise | null
  diasAteSaturar: number | null
}

/** Apresenta somente os valores atuais fornecidos pela API.
 * @param props Refil ativo e estado consolidado recebido do backend.
 * @returns Dados atuais ou orientação para registrar o primeiro refil.
 */
export default function ResumoRefil({
  refil,
  percentualAtual,
  status,
  diasAteSaturar,
}: ResumoRefilProps) {
  return (
    <section
      aria-labelledby="titulo-refil-ativo"
      className="surface-panel rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6"
    >
      <p className="section-kicker">
        Ciclo atual
      </p>
      <h2
        className="section-title"
        id="titulo-refil-ativo"
      >
        Refil ativo
      </h2>
      {refil ? (
        <>
          <dl className="mt-4 grid grid-cols-2 gap-4">
            <div>
              <dt className="text-sm font-medium text-slate-700">Instalado em</dt>
              <dd className="mt-1 break-words font-semibold text-slate-950">
                {formatData(refil.data_instalacao)}
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-slate-700">Dias em uso</dt>
              <dd className="mt-1 break-words font-semibold text-slate-950">
                {refil.dias_em_uso} {refil.dias_em_uso === 1 ? 'dia' : 'dias'}
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-slate-700">Cobertura atual</dt>
              <dd className="mt-1 break-words font-semibold text-slate-950">
                {formatPercentual(percentualAtual)}
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-slate-700">Estimativa</dt>
              <dd className="mt-1 break-words font-semibold text-slate-950">
                {formatDiasAteSaturar(diasAteSaturar)}
              </dd>
            </div>
          </dl>
          <div className="mt-4">
            {status ? (
              <StatusBadge status={status} />
            ) : (
              <p className="text-sm text-slate-700">Ainda não há análises neste ciclo.</p>
            )}
          </div>
        </>
      ) : (
        <p className="mt-3 text-sm leading-6 text-slate-700">
          Sem refil ativo. Registre um refil para iniciar o acompanhamento da cobertura.
        </p>
      )}
    </section>
  )
}
