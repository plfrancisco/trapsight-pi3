import { formatPercentual } from '../lib/formatacao'
import { formatIndiceSaturacao } from '../lib/saturacao'
import type { Analise } from '../services/tipos'
import ImagemAnalise from './ImagemAnalise'
import StatusBadge from './StatusBadge'

interface ResultadoAnaliseProps {
  analise: Analise
}

/** Apresenta os dados do processamento e a imagem com a identificação do modelo. */
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
          <div className="sm:text-right">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">
              Saturação do refil
            </p>
            <p className="text-3xl font-bold tabular-nums tracking-tight text-emerald-950">
              {formatIndiceSaturacao(analise.percentual_coberto)}
            </p>
            <p className="text-sm text-slate-700">
              {formatPercentual(analise.percentual_coberto)} da placa coberta
            </p>
          </div>
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
            Imagem analisada
          </figcaption>
          <ImagemAnalise
            analiseId={analise.id}
            descricao="enviada para análise da armadilha"
            height={480}
            imagemClassName="size-full object-contain"
            moldura="aspect-[4/3] max-h-[36rem] overflow-hidden rounded-xl border border-slate-200 bg-slate-100"
            permitirAlternar
            width={640}
          />
        </figure>
      </div>
    </section>
  )
}
