import { Link } from 'react-router'
import type { ArmadilhaLista } from '../services/tipos'
import { calculateDiasEmAlerta } from '../lib/alertas'

interface PainelAlertasProps {
  armadilhas: ArmadilhaLista[] | null
  carregando: boolean
  erro: boolean
  instanteReferencia: Date
}

/** Mantém a situação dos alertas visível e lista as armadilhas que exigem ação.
 * @param props Dados carregados, estado da consulta e instante de referência.
 * @returns O painel com contagem, estados de consulta e alertas ativos.
 */
export default function PainelAlertas({
  armadilhas,
  carregando,
  erro,
  instanteReferencia,
}: PainelAlertasProps) {
  const consultaConcluida = !carregando && !erro
  const alertas = consultaConcluida
    ? (armadilhas ?? []).filter((armadilha) => armadilha.status === 'trocar')
    : []

  return (
    <section
      aria-labelledby="titulo-painel-alertas"
      className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.14em] text-slate-600">
            Acompanhamento operacional
          </p>
          <h2
            className="mt-1 text-xl font-semibold tracking-tight text-slate-950"
            id="titulo-painel-alertas"
          >
            Alertas de troca
          </h2>
        </div>
        {consultaConcluida ? (
          <p className="text-sm font-medium text-slate-700">
            {alertas.length === 1
              ? '1 armadilha precisa de ação'
              : `${alertas.length} armadilhas precisam de ação`}
          </p>
        ) : null}
      </div>

      {carregando ? (
        <p className="mt-4 text-sm leading-6 text-slate-700" role="status">
          Consultando alertas…
        </p>
      ) : null}
      {erro ? (
        <p className="mt-4 text-sm leading-6 text-slate-700">
          Não foi possível consultar os alertas agora.
        </p>
      ) : null}
      {consultaConcluida && alertas.length === 0 ? (
        <p className="mt-4 rounded-xl bg-emerald-50 px-4 py-3 text-sm font-medium leading-6 text-emerald-950">
          Nenhuma ação é necessária neste momento.
        </p>
      ) : null}
      {consultaConcluida && alertas.length > 0 ? (
        <ul className="mt-4 divide-y divide-slate-200">
          {alertas.map((armadilha) => {
            const diasEmAlerta = armadilha.em_alerta_desde
              ? calculateDiasEmAlerta(
                  armadilha.em_alerta_desde,
                  instanteReferencia,
                )
              : null

            return (
              <li
                className="flex flex-col gap-2 py-3 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between"
                key={armadilha.id}
              >
                <div>
                  <Link
                    aria-label={`Ver detalhes da armadilha ${armadilha.identificador}`}
                    className="rounded font-semibold text-emerald-950 underline decoration-emerald-700 underline-offset-4 hover:text-emerald-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-800"
                    to={`/armadilhas/${armadilha.id}`}
                  >
                    {armadilha.identificador}
                  </Link>
                  <p className="mt-1 text-sm text-slate-700">
                    {armadilha.localizacao ?? 'Localização não informada'}
                  </p>
                </div>
                <p className="text-sm font-medium text-slate-700">
                  {diasEmAlerta === null
                    ? 'Data do alerta indisponível'
                    : diasEmAlerta === 0
                      ? 'Em alerta desde hoje'
                      : `Em alerta há ${diasEmAlerta} ${diasEmAlerta === 1 ? 'dia' : 'dias'}`}
                </p>
              </li>
            )
          })}
        </ul>
      ) : null}
    </section>
  )
}
