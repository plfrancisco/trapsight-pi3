import { Link } from 'react-router'
import { formatDataHora, formatDiasAteSaturar } from '../lib/formatacao'
import { PALETA_STATUS } from '../lib/paleta'
import { formatIndiceSaturacao, indiceSaturacao } from '../lib/saturacao'
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
  const indice = percentual === null ? 0 : indiceSaturacao(percentual, armadilha.limiar_trocar)
  const indiceFormatado = formatIndiceSaturacao(percentual, armadilha.limiar_trocar)

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
      <div className="trap-card__body">
        <div className="trap-card__heading">
            <div className="trap-card__photo" title={armadilha.foto_tipo === 'real' ? 'Foto da armadilha' : 'Foto padrão do modelo'}>
              <FotoArmadilha className="trap-card__image" fotoTipo={armadilha.foto_tipo}
                fotoUrl={armadilha.foto_url} identificador={armadilha.identificador}
                key={armadilha.foto_url ?? 'padrao'} modelo={armadilha.modelo} />
            </div>

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
                <p className="trap-card__metric-label">Saturação do refil</p>
                <p className="trap-card__metric-value">{indiceFormatado}</p>
              </div>
              <div className="trap-card__forecast">
                <span className="trap-card__forecast-label">Até saturar</span>
                <strong>{formatDiasAteSaturar(armadilha.dias_ate_saturar)}</strong>
              </div>
            </div>

            <div
              aria-label={`Saturação da armadilha ${armadilha.identificador}`}
              aria-valuemax={100}
              aria-valuemin={0}
              aria-valuenow={indice}
              aria-valuetext={indiceFormatado}
              className="trap-card__progress"
              role="progressbar"
            >
              <span
                className="trap-card__progress-value"
                style={{
                  backgroundColor: armadilha.status
                    ? PALETA_STATUS[armadilha.status].linha
                    : 'var(--app-primary)',
                  width: `${indice}%`,
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
