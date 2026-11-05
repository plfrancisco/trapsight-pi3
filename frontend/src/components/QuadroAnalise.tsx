import { memo } from 'react'
import { formatDataHora, rotuloStatus } from '../lib/formatacao'
import { formatIndiceSaturacao } from '../lib/saturacao'
import type { Analise } from '../services/tipos'
import ImagemAnalise from './ImagemAnalise'
import StatusBadge from './StatusBadge'

interface QuadroAnaliseProps {
  analise: Analise
  indice: number
  quantidade: number
  limiarTrocar?: number
}

/** Apresenta a imagem com a máscara da análise selecionada no gráfico.
 * @param props Análise selecionada e sua posição na sequência cronológica.
 * @returns Imagem e dados acessíveis do quadro atual.
 */
function QuadroAnalise({
  analise,
  indice,
  quantidade,
  limiarTrocar,
}: QuadroAnaliseProps) {
  const dataHora = formatDataHora(analise.analisado_em)
  const percentual = formatIndiceSaturacao(analise.percentual_coberto, limiarTrocar)
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
        Quadro {numeroQuadro} de {quantidade}. {dataHora}. Saturação {percentual}.
        {' '}Status {rotuloStatus(analise.status)}.
      </p>

      <figure className="analysis-frame-card__figure">
        <ImagemAnalise
          analiseId={analise.id}
          descricao={`da análise de ${dataHora}, saturação ${percentual}`}
          height={480}
          imagemClassName="analysis-frame-card__image"
          key={analise.id}
          moldura="analysis-frame-card__image-wrap"
          variante="mascara"
          width={640}
        />
        <figcaption className="analysis-frame-card__caption">
          <span>Quadro {numeroQuadro} de {quantidade}</span>
          <strong>Saturação <b>{percentual}</b></strong>
        </figcaption>
      </figure>
    </section>
  )
}

export default memo(QuadroAnalise)
