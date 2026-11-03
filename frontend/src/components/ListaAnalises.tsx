import { formatDataHora } from '../lib/formatacao'
import { formatIndiceSaturacao } from '../lib/saturacao'
import type { Analise } from '../services/tipos'
import ImagemAnalise from './ImagemAnalise'
import StatusBadge from './StatusBadge'

interface ListaAnalisesProps {
  analises: Analise[]
  historicoCompleto?: boolean
  limiarTrocar?: number
}

/** Exibe medições recentes primeiro e mantém a lista como alternativa ao gráfico.
 * @param props Análises recebidas da API em ordem cronológica crescente.
 * @returns Lista semântica de análises com miniaturas e resultados.
 */
export default function ListaAnalises({
  analises,
  historicoCompleto = false,
  limiarTrocar,
}: ListaAnalisesProps) {
  if (analises.length === 0) return null

  return (
    <section aria-labelledby="titulo-analises">
      <div className="mb-4">
        <p className="section-kicker">
          {historicoCompleto ? 'Histórico completo' : 'Histórico do ciclo atual'}
        </p>
        <h2
          className="section-title"
          id="titulo-analises"
        >
          Análises
        </h2>
      </div>
      <ul className="grid list-none gap-4 p-0 sm:grid-cols-2 lg:grid-cols-3">
        {[...analises].reverse().map((analise) => {
          const instante = formatDataHora(analise.analisado_em)
          const percentual = formatIndiceSaturacao(analise.percentual_coberto, limiarTrocar)

          return (
            <li
              className="surface-panel flex gap-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
              key={analise.id}
            >
              <ImagemAnalise
                analiseId={analise.id}
                descricao={`da análise de ${instante}, saturação de ${percentual}`}
                height={96}
                imagemClassName="size-24 shrink-0 rounded-xl bg-slate-100 object-cover"
                loading="lazy"
                mostrarLegenda={false}
                width={96}
              />
              <div className="min-w-0 space-y-2">
                <h3 className="font-semibold text-slate-950">{instante}</h3>
                <p className="text-sm text-slate-700">Saturação: {percentual}</p>
                <StatusBadge status={analise.status} />
              </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
