import { lazy, Suspense, useCallback, useMemo, useState } from 'react'
import { buildResumoCobertura, buildSerieCobertura } from '../lib/cobertura'
import { formatDataHora, formatPercentual } from '../lib/formatacao'
import { calcularMesPrevistoTroca } from '../lib/previsaoTroca'
import { instanteDoQuadro, mapearArrastoParaIndice } from '../lib/marcadorGrafico'
import { urlImagemAnalise } from '../services/midia'
import type { Analise } from '../services/tipos'
import QuadroAnalise from './QuadroAnalise'
import StatusBadge from './StatusBadge'

const EvolucaoGrafico = lazy(() => import('./EvolucaoGrafico'))

interface EvolucaoCoberturaProps {
  analisesAtivas: Analise[]
  diasAteSaturar?: number | null
  limiarTrocar?: number
}

function ordenarAnalises(analises: readonly Analise[]): Analise[] {
  return [...analises].sort(
    (analiseA, analiseB) =>
      Date.parse(analiseA.analisado_em) - Date.parse(analiseB.analisado_em),
  )
}

function ImagemAnaliseUnica({ analise }: { analise: Analise }) {
  const dataHora = formatDataHora(analise.analisado_em)
  const percentual = formatPercentual(analise.percentual_coberto)

  return (
    <section aria-label="Imagem da análise" className="analysis-frame-card">
      <header className="analysis-frame-card__header">
        <div>
          <p className="analysis-frame-card__eyebrow">Registro mais recente</p>
          <h3>Foto da armadilha</h3>
          <p className="analysis-frame-card__date">{dataHora}</p>
        </div>
        <StatusBadge status={analise.status} />
      </header>
      <figure className="analysis-frame-card__figure">
        <div className="analysis-frame-card__image-wrap">
          <img
            alt={`Imagem da armadilha registrada em ${dataHora}, com ${percentual} de cobertura`}
            className="analysis-frame-card__image"
            decoding="async"
            height={480}
            src={urlImagemAnalise(analise.id)}
            width={640}
          />
        </div>
        <figcaption className="analysis-frame-card__caption">
          <span>Última análise</span>
          <strong>Cobertura <b>{percentual}</b></strong>
        </figcaption>
      </figure>
    </section>
  )
}

/** Sincroniza a foto selecionada com o ponto escolhido no gráfico.
 * @param props Análises do refil ativo e estimativa de troca.
 * @returns Gráfico interativo e foto correspondente à medição atual.
 */
export default function EvolucaoCobertura({
  analisesAtivas,
  diasAteSaturar = null,
  limiarTrocar,
}: EvolucaoCoberturaProps) {
  const analises = useMemo(() => ordenarAnalises(analisesAtivas), [analisesAtivas])
  const [indiceSelecionado, setIndiceSelecionado] = useState(0)
  const indiceVisivel = Math.max(0, Math.min(analises.length - 1, indiceSelecionado))
  const instantes = useMemo(
    () => analises.map((analise) => Date.parse(analise.analisado_em)),
    [analises],
  )
  const serie = useMemo(() => buildSerieCobertura(analises), [analises])
  const resumo = useMemo(() => buildResumoCobertura(analises), [analises])
  const previsaoTroca = useMemo(
    () => calcularMesPrevistoTroca(diasAteSaturar),
    [diasAteSaturar],
  )
  const analiseAtual = analises[indiceVisivel]

  const changeMarcador = useCallback(
    (instante: number) => {
      const indice = mapearArrastoParaIndice(instantes, instante)
      if (indice >= 0) setIndiceSelecionado(indice)
    },
    [instantes],
  )

  if (analises.length === 0) return null

  const possuiGrafico = analises.length >= 2

  return (
    <section
      aria-labelledby="titulo-evolucao"
      className="space-y-4"
    >
      <div>
        <p className="section-kicker">Refil ativo</p>
        <h2 className="section-title" id="titulo-evolucao">
          Evolução da cobertura
        </h2>
        {possuiGrafico ? (
          <p className="mt-2 max-w-2xl text-sm text-app-muted">
            Passe o cursor, toque ou use as setas no gráfico para ver a foto daquela data.
          </p>
        ) : null}
      </div>

      {analiseAtual && possuiGrafico ? (
        <div className="analysis-evolution-grid">
          <Suspense
            fallback={(
              <div
                aria-live="polite"
                className="surface-panel h-96 animate-pulse rounded-[26px]"
                role="status"
              >
                Carregando gráfico…
              </div>
            )}
          >
            <EvolucaoGrafico
              marcador={instanteDoQuadro(instantes, indiceVisivel) ?? undefined}
              onMarcadorChange={changeMarcador}
              previsaoTroca={previsaoTroca}
              limiarTrocar={limiarTrocar}
              resumo={resumo}
              serie={serie}
            />
          </Suspense>
          <QuadroAnalise
            analise={analiseAtual}
            indice={indiceVisivel}
            quantidade={analises.length}
          />
        </div>
      ) : analiseAtual ? (
        <ImagemAnaliseUnica analise={analiseAtual} />
      ) : null}
    </section>
  )
}
