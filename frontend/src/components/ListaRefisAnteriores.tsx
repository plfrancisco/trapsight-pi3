import { formatData } from '../lib/formatacao'
import type { RefilAnterior } from '../services/tipos'

interface ListaRefisAnterioresProps {
  refis: RefilAnterior[]
}

/** Lista os ciclos encerrados com datas e duração informadas pela API.
 * @param props Histórico cronológico de refis da armadilha.
 * @returns Histórico sem conteúdo quando a armadilha ainda não teve trocas.
 */
export default function ListaRefisAnteriores({ refis }: ListaRefisAnterioresProps) {
  if (refis.length === 0) return null

  return (
    <section
      aria-labelledby="titulo-refis-anteriores"
      className="surface-panel rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6"
    >
      <h2 className="section-title" id="titulo-refis-anteriores">
        Refis anteriores
      </h2>
      <ul className="mt-4 divide-y divide-slate-200">
        {refis.map((refil) => (
          <li className="py-3 first:pt-0 last:pb-0" key={refil.id}>
            <p className="font-semibold text-slate-950">
              {formatData(refil.data_instalacao)} – {formatData(refil.data_troca)}
            </p>
            <p className="mt-1 text-sm text-slate-700">
              {refil.dias_ate_troca} {refil.dias_ate_troca === 1 ? 'dia de uso' : 'dias de uso'}
            </p>
          </li>
        ))}
      </ul>
    </section>
  )
}
