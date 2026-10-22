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
  const existemAlertas = alertas.length > 0

  return (
    <section
      aria-labelledby="titulo-painel-alertas"
      className={`alert-panel${existemAlertas ? ' alert-panel--attention' : ' alert-panel--clear'}`}
    >
      <div className="alert-panel__header">
        <div className="alert-panel__title-group">
          <span aria-hidden="true" className="alert-panel__icon">
            <svg className="size-5" fill="none" viewBox="0 0 24 24">
              {existemAlertas ? (
                <path
                  d="M12 3 2.8 19h18.4L12 3Z"
                  stroke="currentColor"
                  strokeLinejoin="round"
                  strokeWidth="1.7"
                />
              ) : (
                <path
                  d="m5 12 4.2 4.2L19 6.5"
                  stroke="currentColor"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                />
              )}
              {existemAlertas ? (
                <path
                  d="M12 8v4.5m0 2.5v.1"
                  stroke="currentColor"
                  strokeLinecap="round"
                  strokeWidth="1.8"
                />
              ) : null}
            </svg>
          </span>
          <div>
            <p className="alert-panel__eyebrow">
              {existemAlertas ? 'Prioridade operacional' : 'Tudo em ordem'}
            </p>
            <h2 className="alert-panel__title" id="titulo-painel-alertas">
              Alertas de troca
            </h2>
          </div>
        </div>
        {consultaConcluida ? (
          <p className="alert-panel__count">
            {alertas.length === 1
              ? '1 armadilha precisa de ação'
              : `${alertas.length} armadilhas precisam de ação`}
          </p>
        ) : null}
      </div>

      {carregando ? (
        <p className="alert-panel__message" role="status">
          Consultando alertas…
        </p>
      ) : null}
      {erro ? (
        <p className="alert-panel__message">
          Não foi possível consultar os alertas agora.
        </p>
      ) : null}
      {consultaConcluida && !existemAlertas ? (
        <p className="alert-panel__message alert-panel__message--clear">
          Nenhuma ação é necessária neste momento.
        </p>
      ) : null}
      {consultaConcluida && existemAlertas ? (
        <ul className="alert-panel__list">
          {alertas.map((armadilha) => {
            const diasEmAlerta = armadilha.em_alerta_desde
              ? calculateDiasEmAlerta(
                  armadilha.em_alerta_desde,
                  instanteReferencia,
                )
              : null

            return (
              <li
                className="alert-panel__item"
                key={armadilha.id}
              >
                <div>
                  <Link
                    aria-label={`Ver detalhes da armadilha ${armadilha.identificador}`}
                    className="alert-panel__link"
                    to={`/armadilhas/${armadilha.id}`}
                  >
                    {armadilha.identificador}
                  </Link>
                  <p className="alert-panel__location">
                    {armadilha.localizacao ?? 'Localização não informada'}
                  </p>
                </div>
                <p className="alert-panel__age">
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
