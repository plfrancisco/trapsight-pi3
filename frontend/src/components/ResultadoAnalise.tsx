import { formatPercentual } from '../lib/formatacao'
import type { Analise } from '../services/tipos'
import { urlImagemAnalise } from '../services/midia'
import StatusBadge from './StatusBadge'

interface ResultadoAnaliseProps {
  analise: Analise
}

/** Apresenta os dados do processamento e a foto original enviada para análise. */
export default function ResultadoAnalise({ analise }: ResultadoAnaliseProps) {
  return (
    <section
      aria-labelledby="titulo-resultado-analise"
      className="surface-panel space-y-5 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-8"
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-slate-600">
            Resultado do processamento
          </p>
          <h2
            className="mt-1 text-2xl font-semibold tracking-tight text-slate-950"
            id="titulo-resultado-analise"
          >
            Resultado da análise
          </h2>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <p className="text-3xl font-bold tabular-nums tracking-tight text-emerald-950">
            {formatPercentual(analise.percentual_coberto)}
          </p>
          <StatusBadge status={analise.status} />
        </div>
      </div>

      <dl className="rounded-xl bg-stone-50 px-4 py-3">
        <dt className="text-xs font-semibold uppercase tracking-wide text-slate-600">
          Versão do modelo
        </dt>
        <dd className="mt-1 break-all font-mono text-sm font-medium text-slate-900">
          {analise.modelo_versao}
        </dd>
      </dl>

      <div className="grid gap-5">
        <figure className="min-w-0">
          <figcaption className="mb-2 text-sm font-semibold text-slate-900">
            Imagem original
          </figcaption>
          <div className="aspect-[4/3] max-h-[36rem] overflow-hidden rounded-xl border border-slate-200 bg-slate-100">
            <img
              alt="Imagem original enviada para análise da armadilha"
              className="size-full object-contain"
              height={480}
              src={urlImagemAnalise(analise.id)}
              width={640}
            />
          </div>
        </figure>
      </div>
    </section>
  )
}
