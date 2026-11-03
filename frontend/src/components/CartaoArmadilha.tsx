import { Link } from 'react-router'
import { formatDataHora, formatDiasAteSaturar } from '../lib/formatacao'
import { formatIndiceSaturacao, indiceSaturacao } from '../lib/saturacao'
import type { ArmadilhaLista } from '../services/tipos'
import FotoArmadilha from './FotoArmadilha'
import StatusBadge from './StatusBadge'

interface CartaoArmadilhaProps {
  armadilha: ArmadilhaLista
}

const RAIO_MEDIDOR = 22
const COMPRIMENTO_MEDIDOR = 2 * Math.PI * RAIO_MEDIDOR

/** Resume identificação visual, saturação e prazo recebido para a armadilha. */
export default function CartaoArmadilha({ armadilha }: CartaoArmadilhaProps) {
  const semRefil = armadilha.refil_ativo === null
  const semAnalise = armadilha.ultima_analise_em === null
  const temLeitura = armadilha.percentual_atual !== null && !semRefil && !semAnalise
  const indice = armadilha.percentual_atual !== null && !semRefil && !semAnalise
    ? indiceSaturacao(armadilha.percentual_atual, armadilha.limiar_trocar)
    : 0
  const indiceFormatado = armadilha.percentual_atual !== null && !semRefil && !semAnalise
    ? formatIndiceSaturacao(armadilha.percentual_atual, armadilha.limiar_trocar)
    : '—'
  const localizacao = armadilha.localizacao ?? 'Localização não informada'

  return (
    <Link
      aria-label={`Ver detalhes da armadilha ${armadilha.identificador}`}
      className="trap-card-link"
      to={`/armadilhas/${armadilha.id}`}
    >
      <article aria-labelledby={`titulo-${armadilha.id}`} className="trap-card">
        <div className="trap-card__body">
          <div className="trap-card__heading">
            <div
              className="trap-card__photo"
              title={armadilha.foto_tipo === 'real' ? 'Foto da armadilha' : 'Foto padrão do modelo'}
            >
              <FotoArmadilha
                className="trap-card__image"
                fotoTipo={armadilha.foto_tipo}
                fotoUrl={armadilha.foto_url}
                identificador={armadilha.identificador}
                key={armadilha.foto_url ?? 'padrao'}
                modelo={armadilha.modelo}
              />
            </div>
            <div className="trap-card__identity">
              <h3 className="trap-card__title" id={`titulo-${armadilha.id}`}>
                {armadilha.identificador}
              </h3>
              <p className="trap-card__location" title={localizacao}>{localizacao}</p>
            </div>
            {!semRefil && armadilha.status ? <StatusBadge status={armadilha.status} /> : null}
          </div>

          <div className="trap-card__reading">
            <div
              aria-label={temLeitura
                ? `Índice de saturação ${indiceFormatado}`
                : `Sem leitura de saturação para ${armadilha.identificador}`}
              className={`trap-card__gauge${armadilha.status ? ` trap-card__gauge--${armadilha.status}` : ''}${temLeitura ? '' : ' trap-card__gauge--empty'}`}
              role="img"
            >
              <svg aria-hidden="true" fill="none" viewBox="0 0 56 56">
                <circle className="trap-card__gauge-track" cx="28" cy="28" r={RAIO_MEDIDOR} />
                <circle
                  className="trap-card__gauge-value"
                  cx="28"
                  cy="28"
                  r={RAIO_MEDIDOR}
                  style={temLeitura ? {
                    strokeDasharray: `${COMPRIMENTO_MEDIDOR} ${COMPRIMENTO_MEDIDOR}`,
                    strokeDashoffset: COMPRIMENTO_MEDIDOR * (1 - indice / 100),
                  } : undefined}
                />
              </svg>
              <span className="trap-card__gauge-label">{indiceFormatado}</span>
            </div>

            <div className="trap-card__reading-copy">
              {semRefil ? (
                <p className="trap-card__notice">Sem refil ativo</p>
              ) : semAnalise ? (
                <p className="trap-card__notice">Sem análises neste refil</p>
              ) : !temLeitura ? (
                <p className="trap-card__notice">Saturação indisponível</p>
              ) : (
                <>
                  <p className="trap-card__forecast-label">Até saturar</p>
                  <p className="trap-card__forecast-value">
                    {formatDiasAteSaturar(armadilha.dias_ate_saturar)}
                  </p>
                  <p className="trap-card__last-read">
                    Última análise{' '}
                    <time dateTime={armadilha.ultima_analise_em ?? undefined}>
                      {formatDataHora(armadilha.ultima_analise_em!)}
                    </time>
                  </p>
                </>
              )}
            </div>
          </div>

          <div className="trap-card__footer">
            <span aria-hidden="true" className="trap-card__details-link">
              Ver detalhes
              <svg aria-hidden="true" fill="none" viewBox="0 0 20 20">
                <path d="M4 10h12m-5-5 5 5-5 5" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.6" />
              </svg>
            </span>
          </div>
        </div>
      </article>
    </Link>
  )
}
