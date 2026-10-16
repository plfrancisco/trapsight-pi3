import { formatDataHora, formatPercentual } from '../lib/formatacao'
import type { Analise } from '../services/tipos'
import { urlImagemAnalise } from '../services/midia'
import StatusBadge from './StatusBadge'

interface ListaAnalisesProps {
  analises: Analise[]
}

/** Exibe medições recentes primeiro e mantém a lista como alternativa ao gráfico.
 * @param props Análises recebidas da API em ordem cronológica crescente.
 * @returns Lista semântica de análises com miniaturas e resultados.
 */
export default function ListaAnalises({ analises }: ListaAnalisesProps) {
  if (analises.length === 0) return null

  return (
    <section aria-labelledby="titulo-analises">
      <div className="mb-4">
        <p className="text-sm font-semibold uppercase tracking-wide text-slate-600">
          Histórico do ciclo atual
        </p>
        <h2
          className="mt-1 text-2xl font-semibold tracking-tight text-slate-950"
          id="titulo-analises"
        >
          Análises
        </h2>
      </div>
      <ul className="grid list-none gap-4 p-0 sm:grid-cols-2 lg:grid-cols-3">
        {[...analises].reverse().map((analise) => {
          const instante = formatDataHora(analise.analisado_em)
          const percentual = formatPercentual(analise.percentual_coberto)

          return (
            <li
              className="flex gap-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
              key={analise.id}
            >
              <img
                alt={`Imagem original da análise de ${instante}, cobertura de ${percentual}`}
                className="size-24 shrink-0 rounded-xl bg-slate-100 object-cover"
                height={96}
                loading="lazy"
                src={urlImagemAnalise(analise.id)}
                width={96}
              />
              <div className="min-w-0 space-y-2">
                <h3 className="font-semibold text-slate-950">{instante}</h3>
                <p className="text-sm text-slate-700">Cobertura: {percentual}</p>
                <StatusBadge status={analise.status} />
              </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
