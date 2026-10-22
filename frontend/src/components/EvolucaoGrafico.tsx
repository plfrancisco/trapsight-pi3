import { memo, useCallback, useId, useRef, type KeyboardEvent } from 'react'
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { LIMIAR_ATENCAO, LIMIAR_TROCAR } from '../lib/limiares'
import { PALETA_STATUS } from '../lib/paleta'
import type { PontoCobertura } from '../lib/cobertura'
import { formatPercentual } from '../lib/formatacao'
import type { MesPrevistoTroca } from '../lib/previsaoTroca'

interface EvolucaoGraficoProps {
  serie: PontoCobertura[]
  resumo: string
  marcador?: number
  previsaoTroca?: MesPrevistoTroca | null
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
 * @returns Gráfico responsivo de cobertura no ciclo ativo.
 */
function EvolucaoGrafico({
  serie,
  resumo,
  marcador,
  previsaoTroca = null,
  onMarcadorChange,
}: EvolucaoGraficoProps) {
  const arrastando = useRef(false)
  const gradienteId = `cobertura-${useId().replaceAll(':', '')}`
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
      <div className="evolution-chart-card__header">
        <div className="evolution-chart-card__series">
          <span aria-hidden="true" className="evolution-chart-card__series-mark" />
          <span>Cobertura medida</span>
        </div>
        {previsaoTroca ? (
          <div className="evolution-chart-card__forecast">
            <span aria-hidden="true" className="evolution-chart-card__forecast-mark" />
            <span className="evolution-chart-card__forecast-copy">
              <span>Previsão de troca</span>
              <strong>{previsaoTroca.rotulo}</strong>
              <small>Estimativa ao atingir 70% de cobertura</small>
            </span>
          </div>
        ) : null}
      </div>
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
            <defs>
              <linearGradient id={gradienteId} x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="var(--app-primary)" stopOpacity={0.25} />
                <stop offset="72%" stopColor="var(--app-primary)" stopOpacity={0.08} />
                <stop offset="100%" stopColor="var(--app-primary)" stopOpacity={0.01} />
              </linearGradient>
            </defs>
            <CartesianGrid
              horizontal
              stroke="var(--app-line)"
              strokeDasharray="3 7"
              vertical={false}
            />
            {previsaoTroca ? (
              <ReferenceArea
                x1={previsaoTroca.inicio}
                x2={previsaoTroca.fim}
                y1={0}
                y2={100}
                fill="var(--app-attention-soft)"
                fillOpacity={0.12}
                strokeOpacity={0}
              />
            ) : null}
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
              axisLine={false}
              tickLine={false}
              tick={{ fill: 'var(--app-muted)', fontSize: 11 }}
              tickMargin={8}
              tickFormatter={(valor: number) => `${valor}%`}
            />
            <Tooltip
              contentStyle={{
                border: '1px solid var(--app-line)',
                borderRadius: 14,
                color: 'var(--app-text)',
                background: 'var(--app-surface)',
                boxShadow: 'var(--app-shadow-control)',
              }}
              cursor={{ stroke: 'var(--app-primary)', strokeDasharray: '4 4' }}
              formatter={(valor) => [formatPercentual(Number(valor)), 'Cobertura']}
              labelFormatter={(valor) => formatTooltipData(Number(valor))}
              labelStyle={{ color: 'var(--app-muted)' }}
              itemStyle={{ color: 'var(--app-primary-strong)' }}
            />
            <Area
              dataKey="percentual"
              fill={`url(#${gradienteId})`}
              isAnimationActive={false}
              stroke="none"
              type="linear"
            />
            <ReferenceLine
              label={{
                value: 'Atenção',
                position: 'insideTopRight',
                fill: PALETA_STATUS.atencao.texto,
                fontSize: 12,
                fontWeight: 700,
              }}
              stroke={PALETA_STATUS.atencao.linha}
              strokeDasharray="6 4"
              strokeOpacity={0.72}
              y={LIMIAR_ATENCAO}
            />
            <ReferenceLine
              label={{
                value: 'Trocar',
                position: 'insideTopRight',
                fill: PALETA_STATUS.trocar.texto,
                fontSize: 12,
                fontWeight: 700,
              }}
              stroke={PALETA_STATUS.trocar.linha}
              strokeDasharray="6 4"
              strokeOpacity={0.72}
              y={LIMIAR_TROCAR}
            />
            {marcador === undefined ? null : (
              <ReferenceLine stroke={PALETA_STATUS.ok.linha} x={marcador} />
            )}
            <Line
              activeDot={{
                r: 7,
                fill: 'var(--app-surface)',
                stroke: 'var(--app-primary-strong)',
                strokeWidth: 3,
              }}
              dataKey="percentual"
              dot={{
                fill: 'var(--app-surface)',
                r: 4,
                stroke: 'var(--app-primary-strong)',
                strokeWidth: 2.5,
              }}
              name="Cobertura"
              stroke="var(--app-primary-strong)"
              strokeWidth={3.25}
              type="linear"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export default memo(EvolucaoGrafico)
