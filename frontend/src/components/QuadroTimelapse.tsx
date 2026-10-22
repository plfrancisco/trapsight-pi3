import { memo } from 'react'
import { formatDataHora, formatPercentual, rotuloStatus } from '../lib/formatacao'
import type { Analise } from '../services/tipos'
import { urlImagemAnalise, urlMascaraAnalise } from '../services/midia'
import StatusBadge from './StatusBadge'

interface QuadroTimelapseProps {
  analise: Analise
  indice: number
  quantidade: number
  reproduzindo: boolean
}

/** Apresenta a análise atual e mantém suas imagens estáveis entre quadros.
 * @param props Análise selecionada, posição na sequência e estado de reprodução.
 * @returns Imagem original, máscara e dados acessíveis do quadro atual.
 */
function QuadroTimelapse({
  analise,
  indice,
  quantidade,
  reproduzindo,
}: QuadroTimelapseProps) {
  const dataHora = formatDataHora(analise.analisado_em)
  const percentual = formatPercentual(analise.percentual_coberto)
  const numeroQuadro = indice + 1

  return (
    <section
      aria-labelledby="titulo-quadro-timelapse"
      className="surface-panel rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6"
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3
            className="text-lg font-semibold text-slate-950"
            id="titulo-quadro-timelapse"
          >
            Quadro {numeroQuadro} de {quantidade}
          </h3>
          <p className="mt-1 text-sm text-slate-700">{dataHora}</p>
        </div>
        <div className="space-y-2 text-right">
          <p className="font-semibold text-slate-950">Cobertura: {percentual}</p>
          <StatusBadge status={analise.status} />
        </div>
      </header>

      <p aria-atomic="true" aria-live={reproduzindo ? 'off' : 'polite'} className="sr-only">
        Quadro {numeroQuadro} de {quantidade}. {dataHora}. Cobertura {percentual}.
        {' '}Status {rotuloStatus(analise.status)}.
      </p>

      <div className="mt-5 grid gap-4 md:grid-cols-2">
        <figure className="min-w-0">
          <figcaption className="mb-2 text-sm font-semibold text-slate-800">
            Imagem original
          </figcaption>
          <img
            alt={`Imagem original da análise de ${dataHora}, cobertura ${percentual}`}
            className="aspect-[4/3] w-full rounded-xl bg-slate-100 object-contain"
            decoding="async"
            height={480}
            src={urlImagemAnalise(analise.id)}
            width={640}
          />
        </figure>
        <figure className="min-w-0">
          <figcaption className="mb-2 text-sm font-semibold text-slate-800">
            Máscara
          </figcaption>
          <img
            alt={`Máscara da análise de ${dataHora}, cobertura ${percentual}`}
            className="aspect-[4/3] w-full rounded-xl bg-slate-100 object-contain"
            decoding="async"
            height={480}
            src={urlMascaraAnalise(analise.id)}
            width={640}
          />
        </figure>
      </div>
    </section>
  )
}

export default memo(QuadroTimelapse)
