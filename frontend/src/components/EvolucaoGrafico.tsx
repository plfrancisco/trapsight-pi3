import { memo, useCallback, useRef, type KeyboardEvent } from 'react'
import {
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { LIMIAR_ATENCAO, LIMIAR_TROCAR } from '../lib/limiares'
import { PALETA_STATUS } from '../lib/paleta'
import type { PontoCobertura } from '../lib/cobertura'
import { indiceSaturacao } from '../lib/saturacao'
import { formatPercentual } from '../lib/formatacao'
import type { MesPrevistoTroca } from '../lib/previsaoTroca'

interface EvolucaoGraficoProps {
  serie: PontoCobertura[]
  resumo: string
  marcador?: number
  previsaoTroca?: MesPrevistoTroca | null
  limiarTrocar?: number
  onMarcadorChange?: (instante: number) => void
}

interface EstadoInteracaoGrafico {
  activeLabel: string | number | undefined
}

function formatEixoData(instante: number): string {
  return new Date(instante).toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: 'short',
  })
}

function formatTooltipData(instante: number): string {
  return new Date(instante).toLocaleString('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'short',
  })
}

/** Renderiza a série fornecida com limiares e um marcador temporal opcional.
 * @param props Série já transformada, rótulo acessível e marcador em milissegundos.
 * @returns Gráfico responsivo de saturação no ciclo ativo.
 */
function EvolucaoGrafico({
  serie,
  resumo,
  marcador,
  previsaoTroca = null,
  limiarTrocar = LIMIAR_TROCAR,
  onMarcadorChange,
}: EvolucaoGraficoProps) {
  // A conversão existente mantém atenção em 40 e troca em 80 na escala do gráfico.
  const indiceAtencao = indiceSaturacao(LIMIAR_ATENCAO, limiarTrocar)
  const indiceTroca = indiceSaturacao(limiarTrocar, limiarTrocar)
  const niveisEixo = [...new Set([0, indiceAtencao, indiceTroca, 100])].sort((a, b) => a - b)
  const arrastando = useRef(false)
  const primeiroInstante = serie[0]?.instante ?? 0
  const ultimoInstante = serie.at(-1)?.instante ?? primeiroInstante
  const dominioInstante: [number, number] = [
    Math.min(primeiroInstante, previsaoTroca?.inicio ?? primeiroInstante),
    Math.max(
      serie.length === 1 ? ultimoInstante + 60_000 : ultimoInstante,
      previsaoTroca?.fim ?? ultimoInstante,
    ),
  ]

  if (serie.length === 1 && previsaoTroca === null) {
    dominioInstante[0] = primeiroInstante - 60_000
  }

  const resumoAcessivel = previsaoTroca
    ? `${resumo}. Troca prevista em ${previsaoTroca.rotulo}.`
    : resumo

  const enviarInstanteAtivo = useCallback(
    ({ activeLabel }: EstadoInteracaoGrafico) => {
      const instante =
        typeof activeLabel === 'number'
          ? activeLabel
          : typeof activeLabel === 'string' && activeLabel.trim() !== ''
            ? Number(activeLabel)
            : Number.NaN
      if (Number.isFinite(instante)) onMarcadorChange?.(instante)
    },
    [onMarcadorChange],
  )

  const iniciarArrasto = useCallback(
    (estado: EstadoInteracaoGrafico) => {
      arrastando.current = true
      enviarInstanteAtivo(estado)
    },
    [enviarInstanteAtivo],
  )

  const moverArrasto = useCallback(
    (estado: EstadoInteracaoGrafico) => {
      if (arrastando.current) enviarInstanteAtivo(estado)
    },
    [enviarInstanteAtivo],
  )

  const moverPonteiro = useCallback(
    (estado: EstadoInteracaoGrafico) => {
      const instante =
        typeof estado.activeLabel === 'number'
          ? estado.activeLabel
          : typeof estado.activeLabel === 'string'
            ? Number(estado.activeLabel)
            : Number.NaN
      if (!Number.isFinite(instante) || instante === marcador) return
      enviarInstanteAtivo(estado)
    },
    [enviarInstanteAtivo, marcador],
  )

  const finalizarArrasto = useCallback(() => {
    arrastando.current = false
  }, [])

  const selecionarPonto = useCallback(
    (estado: EstadoInteracaoGrafico) => {
      enviarInstanteAtivo(estado)
    },
    [enviarInstanteAtivo],
  )

  const selecionarComTeclado = useCallback(
    (evento: KeyboardEvent<HTMLDivElement>) => {
      if (evento.key !== 'ArrowLeft' && evento.key !== 'ArrowRight') return
      evento.preventDefault()

      const indiceAtual = serie.findIndex((ponto) => ponto.instante === marcador)
      const indiceBase = indiceAtual < 0 ? 0 : indiceAtual
      const deslocamento = evento.key === 'ArrowRight' ? 1 : -1
      const proximoIndice = Math.max(0, Math.min(serie.length - 1, indiceBase + deslocamento))
      const ponto = serie[proximoIndice]

      if (ponto) onMarcadorChange?.(ponto.instante)
    },
    [marcador, onMarcadorChange, serie],
  )

  return (
    <div
      aria-label={resumoAcessivel}
      className="evolution-chart-card w-full min-w-0 touch-pan-y"
      aria-keyshortcuts="ArrowLeft ArrowRight"
      aria-roledescription="gráfico interativo"
      onKeyDown={selecionarComTeclado}
      role="group"
      tabIndex={0}
    >
      {previsaoTroca ? (
        <div className="evolution-chart-card__header">
          <div className="evolution-chart-card__forecast">
            <span aria-hidden="true" className="evolution-chart-card__forecast-mark" />
            <span className="evolution-chart-card__forecast-copy">
              <span>Previsão de troca</span>
              <strong>{previsaoTroca.rotulo}</strong>
              <small>Estimativa ao atingir {indiceTroca.toLocaleString('pt-BR')}% de saturação</small>
            </span>
          </div>
        </div>
      ) : null}
      <div className="evolution-chart-card__plot">
        <ResponsiveContainer height="100%" width="100%">
          <ComposedChart
            data={serie}
            margin={{ top: 16, right: 14, bottom: 4, left: -12 }}
            onClick={selecionarPonto}
            onMouseDown={iniciarArrasto}
            onMouseLeave={finalizarArrasto}
            onMouseMove={moverPonteiro}
            onMouseUp={finalizarArrasto}
            onTouchEnd={finalizarArrasto}
            onTouchMove={moverArrasto}
            onTouchStart={iniciarArrasto}
          >
            <ReferenceArea
              y1={0}
              y2={indiceAtencao}
              fill="var(--app-status-ok-soft)"
              fillOpacity={0.58}
              strokeOpacity={0}
            />
            <ReferenceArea
              y1={indiceAtencao}
              y2={indiceTroca}
              fill="var(--app-attention-soft)"
              fillOpacity={0.58}
              strokeOpacity={0}
            />
            <ReferenceArea
              y1={indiceTroca}
              y2={100}
              fill="var(--app-danger-soft)"
              fillOpacity={0.58}
              strokeOpacity={0}
            />
            {previsaoTroca ? (
              <ReferenceArea
                x1={previsaoTroca.inicio}
                x2={previsaoTroca.fim}
                y1={0}
                y2={100}
                fill="var(--app-chart)"
                fillOpacity={0.06}
                strokeOpacity={0}
              />
            ) : null}
            <CartesianGrid horizontal stroke="var(--app-line)" vertical={false} />
            <XAxis
              dataKey="instante"
              domain={dominioInstante}
              scale="time"
              tickFormatter={formatEixoData}
              axisLine={false}
              tickLine={false}
              tick={{ fill: 'var(--app-muted)', fontSize: 11 }}
              tickMargin={12}
              type="number"
            />
            <YAxis
              domain={[0, 100]}
              ticks={niveisEixo}
              axisLine={false}
              tickLine={false}
              tick={{ fill: 'var(--app-muted)', fontSize: 11 }}
              tickMargin={8}
              tickFormatter={(valor: number) => `${valor}%`}
            />
            <Tooltip
              contentStyle={{
                border: '1px solid var(--app-line)',
                borderRadius: 8,
                color: 'var(--app-text)',
                background: 'var(--app-surface)',
                boxShadow: 'none',
              }}
              cursor={{ stroke: 'var(--app-primary)', strokeDasharray: '4 4' }}
              formatter={(valor) => [formatPercentual(Number(valor)), 'Saturação']}
              labelFormatter={(valor) => formatTooltipData(Number(valor))}
              labelStyle={{ color: 'var(--app-muted)' }}
              itemStyle={{ color: 'var(--app-chart)' }}
            />
            <ReferenceLine
              label={{
                value: `Atenção · ${indiceAtencao.toLocaleString('pt-BR', { maximumFractionDigits: 0 })}%`,
                position: 'insideTopRight',
                fill: PALETA_STATUS.atencao.texto,
                fontSize: 12,
                fontWeight: 500,
              }}
              stroke={PALETA_STATUS.atencao.linha}
              strokeDasharray="5 5"
              y={indiceAtencao}
            />
            <ReferenceLine
              label={{
                value: `Trocar · ${indiceTroca.toLocaleString('pt-BR', { maximumFractionDigits: 0 })}%`,
                position: 'insideTopRight',
                fill: PALETA_STATUS.trocar.texto,
                fontSize: 12,
                fontWeight: 500,
              }}
              stroke={PALETA_STATUS.trocar.linha}
              strokeDasharray="5 5"
              y={indiceTroca}
            />
            {marcador === undefined ? null : (
              <ReferenceLine stroke="var(--app-chart)" x={marcador} />
            )}
            <Line
              isAnimationActive={false}
              activeDot={{
                r: 6,
                fill: 'var(--app-surface)',
                stroke: 'var(--app-chart)',
                strokeWidth: 2.5,
              }}
              dataKey="percentual"
              dot={false}
              name="Saturação"
              stroke="var(--app-chart)"
              strokeWidth={2.5}
              type="linear"
            />
            {serie.length > 0 ? (
              <ReferenceDot
                x={serie.at(-1)?.instante}
                y={serie.at(-1)?.percentual}
                fill="var(--app-chart)"
                r={3.5}
                stroke="var(--app-surface)"
                strokeWidth={2}
              />
            ) : null}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export default memo(EvolucaoGrafico)
