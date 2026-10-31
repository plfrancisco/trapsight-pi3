import { Link } from 'react-router'
import { formatDataHora, formatDiasAteSaturar, formatPercentual } from '../lib/formatacao'
import { PALETA_STATUS } from '../lib/paleta'
import type { ArmadilhaLista } from '../services/tipos'
import FotoArmadilha from './FotoArmadilha'
import StatusBadge from './StatusBadge'

interface CartaoArmadilhaProps {
  armadilha: ArmadilhaLista
}

/** Resume estado, foto de identificação e urgência operacional de uma armadilha.
 * @param props Armadilha consolidada recebida da API.
 * @returns Um cartão com imagem, medição atual e acesso aos detalhes.
 */
export default function CartaoArmadilha({ armadilha }: CartaoArmadilhaProps) {
  const semRefil = armadilha.refil_ativo === null
  const semAnalise = armadilha.ultima_analise_em === null
  const percentual = armadilha.percentual_atual
  const percentualSeguro = Math.min(100, Math.max(0, percentual ?? 0))

  return (
    <Link
      aria-label={`Ver detalhes da armadilha ${armadilha.identificador}`}
      className="trap-card-link"
      to={`/armadilhas/${armadilha.id}`}
    >
    <article
      aria-labelledby={`titulo-${armadilha.id}`}
      className="trap-card"
    >
      <div className="trap-card__photo">
        <FotoArmadilha
          className="trap-card__image"
          fotoTipo={armadilha.foto_tipo}
          fotoUrl={armadilha.foto_url}
          identificador={armadilha.identificador}
          key={armadilha.foto_url ?? 'padrao'}
          modelo={armadilha.modelo}
        />
        <div aria-hidden="true" className="trap-card__photo-scrim" />
        <span className="trap-card__photo-label">
          <svg aria-hidden="true" className="size-3.5" fill="none" viewBox="0 0 20 20">
            <rect height="12" rx="2" stroke="currentColor" strokeWidth="1.4" width="14" x="3" y="4" />
            <circle cx="7.5" cy="8" r="1.2" stroke="currentColor" strokeWidth="1.2" />
            <path d="m5 14 3.5-3 2.5 2 2-1.5 2 2.5" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.2" />
          </svg>
          {armadilha.foto_tipo === 'real' ? 'Foto da armadilha' : 'Foto padrão do modelo'}
        </span>
        <span className="trap-card__photo-index">
          {armadilha.identificador}
        </span>
      </div>

      <div className="trap-card__body">
        <div className="trap-card__heading">
          <div className="min-w-0">
            <h3 className="trap-card__title" id={`titulo-${armadilha.id}`}>
              {armadilha.identificador}
            </h3>
            <p className="trap-card__location">
              <svg aria-hidden="true" className="size-4 shrink-0" fill="none" viewBox="0 0 20 20">
                <path d="M16 8.3c0 4-6 8.7-6 8.7S4 12.3 4 8.3a6 6 0 1 1 12 0Z" stroke="currentColor" strokeWidth="1.4" />
                <circle cx="10" cy="8" r="1.8" stroke="currentColor" strokeWidth="1.4" />
              </svg>
              <span>{armadilha.localizacao ?? 'Localização não informada'}</span>
            </p>
          </div>
          {!semRefil && armadilha.status ? <StatusBadge status={armadilha.status} /> : null}
        </div>

        {semRefil ? (
          <p className="trap-card__notice">
            <span aria-hidden="true" className="trap-card__notice-dot" />
            Sem refil ativo
          </p>
        ) : semAnalise ? (
          <p className="trap-card__notice">
            <span aria-hidden="true" className="trap-card__notice-dot" />
            Sem análises neste refil
          </p>
        ) : (
          <>
            <div className="trap-card__reading">
              <div>
                <p className="trap-card__metric-label">Cobertura atual</p>
                <p className="trap-card__metric-value">{formatPercentual(percentual)}</p>
              </div>
              <div className="trap-card__forecast">
                <span className="trap-card__forecast-label">Até saturar</span>
                <strong>{formatDiasAteSaturar(armadilha.dias_ate_saturar)}</strong>
              </div>
            </div>

            <div
              aria-label={`Cobertura da armadilha ${armadilha.identificador}`}
              aria-valuemax={100}
              aria-valuemin={0}
              aria-valuenow={percentualSeguro}
              aria-valuetext={formatPercentual(percentual)}
              className="trap-card__progress"
              role="progressbar"
            >
              <span
                className="trap-card__progress-value"
                style={{
                  backgroundColor: armadilha.status
                    ? PALETA_STATUS[armadilha.status].linha
                    : '#4C9A68',
                  width: `${percentualSeguro}%`,
                }}
              />
            </div>

            <p className="trap-card__last-read">
              Última análise{' '}
              <time dateTime={armadilha.ultima_analise_em ?? undefined}>
                {armadilha.ultima_analise_em
                  ? formatDataHora(armadilha.ultima_analise_em)
                  : 'Data indisponível'}
              </time>
            </p>
          </>
        )}

        <div className="trap-card__footer">
          <span aria-hidden="true" className="trap-card__details-link">
            Ver detalhes
            <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 20 20">
              <path d="M4 10h12m-5-5 5 5-5 5" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.6" />
            </svg>
          </span>
        </div>
      </div>
    </article>
    </Link>
  )
}
