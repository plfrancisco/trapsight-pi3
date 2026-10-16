import { formatDataHora, formatDiasAteSaturar, formatPercentual } from '../lib/formatacao'
import type { ArmadilhaLista } from '../services/tipos'
import LinkBotao from './LinkBotao'
import StatusBadge from './StatusBadge'

interface CartaoArmadilhaProps {
  armadilha: ArmadilhaLista
}

/** Resume os dados medidos e a urgência operacional de uma armadilha.
 * @param props Armadilha consolidada recebida da API.
 * @returns Um cartão com estado, medição e link para os detalhes.
 */
export default function CartaoArmadilha({ armadilha }: CartaoArmadilhaProps) {
  const semRefil = armadilha.refil_ativo === null

  return (
    <article
      aria-labelledby={`titulo-${armadilha.id}`}
      className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md sm:p-6"
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h3
              className="text-lg font-semibold tracking-tight text-slate-950"
              id={`titulo-${armadilha.id}`}
            >
              {armadilha.identificador}
            </h3>
            {!semRefil && armadilha.status ? (
              <StatusBadge status={armadilha.status} />
            ) : null}
          </div>
          <p className="mt-1 text-sm text-slate-700">
            {armadilha.localizacao ?? 'Localização não informada'}
          </p>
        </div>
        <LinkBotao
          aria-label={`Ver detalhes da armadilha ${armadilha.identificador}`}
          className="text-emerald-950 underline decoration-emerald-700 underline-offset-4 hover:bg-emerald-50"
          tamanho="compacto"
          to={`/armadilhas/${armadilha.id}`}
          variante="discreto"
        >
          Ver detalhes
        </LinkBotao>
      </div>

      {semRefil ? (
        <p className="mt-5 rounded-xl bg-slate-100 px-4 py-3 text-sm font-medium text-slate-800">
          Sem refil ativo
        </p>
      ) : armadilha.status === null ? (
        <div className="mt-5 rounded-xl bg-slate-100 px-4 py-3">
          <p className="text-sm font-medium text-slate-800">Sem análises</p>
        </div>
      ) : (
        <dl className="mt-5 grid gap-4 border-t border-slate-200 pt-4 sm:grid-cols-3">
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-600">
              Cobertura atual
            </dt>
            <dd className="mt-1 text-xl font-semibold tabular-nums text-slate-950">
              {formatPercentual(armadilha.percentual_atual)}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-600">
              Estimativa de saturação
            </dt>
            <dd className="mt-1 text-base font-semibold text-slate-950">
              {formatDiasAteSaturar(armadilha.dias_ate_saturar)}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-600">
              Última análise
            </dt>
            <dd className="mt-1 text-sm font-medium text-slate-800">
              {armadilha.ultima_analise_em
                ? formatDataHora(armadilha.ultima_analise_em)
                : 'Data indisponível'}
            </dd>
          </div>
        </dl>
      )}
    </article>
  )
}
