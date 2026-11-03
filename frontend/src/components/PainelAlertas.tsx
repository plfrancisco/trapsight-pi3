import { Link } from 'react-router'
import { calculateDiasEmAlerta } from '../lib/alertas'
import { formatDiasAteSaturar } from '../lib/formatacao'
import type { ArmadilhaLista } from '../services/tipos'

interface PainelAlertasProps {
  armadilhas: ArmadilhaLista[] | null
  carregando: boolean
  erro: boolean
  instanteReferencia: Date
}

function tempoAteAcao(armadilha: ArmadilhaLista, instanteReferencia: Date): string {
  if (armadilha.status === 'trocar') {
    if (!armadilha.em_alerta_desde) return 'Troca indicada; data indisponível'
    const dias = calculateDiasEmAlerta(armadilha.em_alerta_desde, instanteReferencia)
    if (dias === 0) return 'Saturada hoje'
    return `Saturada há ${dias} ${dias === 1 ? 'dia' : 'dias'}`
  }

  if (armadilha.dias_ate_saturar === null) return 'Previsão indisponível'
  if (armadilha.dias_ate_saturar <= 0) return 'Satura hoje'
  return `Satura em ${formatDiasAteSaturar(armadilha.dias_ate_saturar)}`
}

/** Mantém as armadilhas que precisam de uma ação na ordem de urgência da API. */
export default function PainelAlertas({
  armadilhas,
  carregando,
  erro,
  instanteReferencia,
}: PainelAlertasProps) {
  const consultaConcluida = !carregando && !erro
  const prioridades = consultaConcluida
    ? (armadilhas ?? []).filter(
        (armadilha) => armadilha.status === 'trocar' || armadilha.status === 'atencao',
      )
    : []

  const temTrocaUrgente = prioridades.some((armadilha) => armadilha.status === 'trocar')

  return (
    <section
      aria-labelledby="titulo-painel-alertas"
      className={`alert-panel${temTrocaUrgente ? ' alert-panel--attention' : ''}`}
    >
      <div className="alert-panel__header">
        <div className="alert-panel__title-group">
          <div>
            <p className="alert-panel__eyebrow">A próxima ação da operação</p>
            <h2 className="alert-panel__title" id="titulo-painel-alertas">Fila de ação</h2>
          </div>
        </div>
        {consultaConcluida ? (
          <p aria-live="polite" className="alert-panel__count">
            {prioridades.length === 1 ? '1 ação' : `${prioridades.length} ações`}
          </p>
        ) : null}
      </div>

      {carregando ? (
        <p className="alert-panel__message" role="status">Atualizando prioridades…</p>
      ) : null}
      {erro ? (
        <p className="alert-panel__message" role="status">
          Não foi possível carregar as prioridades agora.
        </p>
      ) : null}
      {consultaConcluida && prioridades.length === 0 ? (
        <p className="alert-panel__message alert-panel__message--clear">
          Nenhuma ação necessária hoje.
        </p>
      ) : null}
      {consultaConcluida && prioridades.length > 0 ? (
        <ul className="alert-panel__list">
          {prioridades.map((armadilha) => {
            const acao = armadilha.status === 'trocar' ? 'Registrar troca' : 'Ver armadilha'

            return (
              <li
                className={`alert-panel__item alert-panel__item--${armadilha.status}`}
                key={armadilha.id}
              >
                <div className="alert-panel__identity">
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
                <div className="alert-panel__status">
                  <span className="alert-panel__status-label">
                    {armadilha.status === 'trocar' ? 'Trocar agora' : 'Atenção'}
                  </span>
                  <p className={`alert-panel__age${armadilha.status === 'trocar' ? ' alert-panel__age--urgent' : ''}`}>
                    {tempoAteAcao(armadilha, instanteReferencia)}
                  </p>
                </div>
                <Link
                  aria-label={`${acao}: ${armadilha.identificador}`}
                  className="alert-panel__action"
                  to={`/armadilhas/${armadilha.id}`}
                >
                  {acao}
                  <svg aria-hidden="true" fill="none" viewBox="0 0 20 20">
                    <path d="M4 10h12m-5-5 5 5-5 5" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" />
                  </svg>
                </Link>
              </li>
            )
          })}
        </ul>
      ) : null}
    </section>
  )
}
