import { memo } from 'react'
import { formatDataHora, formatPercentual, rotuloStatus } from '../lib/formatacao'
import type { Analise } from '../services/tipos'
import { urlImagemAnalise } from '../services/midia'
import StatusBadge from './StatusBadge'

interface QuadroAnaliseProps {
  analise: Analise
  indice: number
  quantidade: number
}

/** Apresenta a foto original da análise selecionada no gráfico.
 * @param props Análise selecionada e sua posição na sequência cronológica.
 * @returns Foto original e dados acessíveis do quadro atual.
 */
function QuadroAnalise({
  analise,
  indice,
  quantidade,
}: QuadroAnaliseProps) {
  const dataHora = formatDataHora(analise.analisado_em)
  const percentual = formatPercentual(analise.percentual_coberto)
  const numeroQuadro = indice + 1

  return (
    <section
      aria-labelledby="titulo-quadro-analise"
      className="analysis-frame-card"
    >
      <header className="analysis-frame-card__header">
        <div>
          <p className="analysis-frame-card__eyebrow">Registro selecionado</p>
          <h3 id="titulo-quadro-analise">Análise {numeroQuadro.toString().padStart(2, '0')}</h3>
          <p className="analysis-frame-card__date">{dataHora}</p>
        </div>
        <StatusBadge status={analise.status} />
      </header>

      <p aria-atomic="true" aria-live="polite" className="sr-only">
        Quadro {numeroQuadro} de {quantidade}. {dataHora}. Cobertura {percentual}.
        {' '}Status {rotuloStatus(analise.status)}.
      </p>

      <figure className="analysis-frame-card__figure">
        <div className="analysis-frame-card__image-wrap">
          <img
            key={analise.id}
            alt={`Imagem original da análise de ${dataHora}, cobertura ${percentual}`}
            className="analysis-frame-card__image"
            decoding="async"
            height={480}
            src={urlImagemAnalise(analise.id)}
            width={640}
          />
        </div>
        <figcaption className="analysis-frame-card__caption">
          <span>Quadro {numeroQuadro} de {quantidade}</span>
          <strong>Cobertura <b>{percentual}</b></strong>
        </figcaption>
      </figure>
    </section>
  )
}

export default memo(QuadroAnalise)
