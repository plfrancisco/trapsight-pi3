import { memo, useCallback, useRef } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
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

interface EvolucaoGraficoProps {
  serie: PontoCobertura[]
  resumo: string
  marcador?: number
  marcasDeTroca?: number[]
  onMarcadorChange?: (instante: number) => void
  onInteracaoManual?: () => void
}

interface EstadoInteracaoGrafico {
  activeLabel: string | number | undefined
}

function formatEixoData(instante: number): string {
  return new Date(instante).toLocaleDateString('pt-BR')
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
  marcasDeTroca = [],
  onMarcadorChange,
  onInteracaoManual,
}: EvolucaoGraficoProps) {
  const arrastando = useRef(false)
  const dominioInstante: [number | 'dataMin', number | 'dataMax'] =
    serie.length === 1
      ? [serie[0].instante - 60_000, serie[0].instante + 60_000]
      : ['dataMin', 'dataMax']

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
      onInteracaoManual?.()
      enviarInstanteAtivo(estado)
    },
    [enviarInstanteAtivo, onInteracaoManual],
  )

  const moverArrasto = useCallback(
    (estado: EstadoInteracaoGrafico) => {
      if (arrastando.current) enviarInstanteAtivo(estado)
    },
    [enviarInstanteAtivo],
  )

  const finalizarArrasto = useCallback(() => {
    arrastando.current = false
  }, [])

  const selecionarPonto = useCallback(
    (estado: EstadoInteracaoGrafico) => {
      onInteracaoManual?.()
      enviarInstanteAtivo(estado)
    },
    [enviarInstanteAtivo, onInteracaoManual],
  )

  return (
    <div
      aria-label={resumo}
      className="surface-panel h-80 w-full touch-pan-y rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
      role="img"
    >
      <ResponsiveContainer height="100%" width="100%">
        <LineChart
          data={serie}
          margin={{ top: 20, right: 16, bottom: 8, left: 0 }}
          onClick={selecionarPonto}
          onMouseDown={iniciarArrasto}
          onMouseLeave={finalizarArrasto}
          onMouseMove={moverArrasto}
          onMouseUp={finalizarArrasto}
          onTouchEnd={finalizarArrasto}
          onTouchMove={moverArrasto}
          onTouchStart={iniciarArrasto}
        >
          <CartesianGrid stroke="var(--app-line)" strokeDasharray="4 4" />
          <XAxis
            dataKey="instante"
            domain={dominioInstante}
            scale="time"
            tickFormatter={formatEixoData}
            tick={{ fill: 'var(--app-muted)', fontSize: 12 }}
            type="number"
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fill: 'var(--app-muted)', fontSize: 12 }}
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
            formatter={(valor) => [formatPercentual(Number(valor)), 'Cobertura']}
            labelFormatter={(valor) => formatTooltipData(Number(valor))}
            labelStyle={{ color: 'var(--app-muted)' }}
            itemStyle={{ color: 'var(--app-primary-strong)' }}
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
            y={LIMIAR_TROCAR}
          />
          {marcasDeTroca.map((instante, indice) => (
            <ReferenceLine
              key={`troca-${indice}-${instante}`}
              label={{
                value: 'Troca',
                position: 'insideTop',
                fill: PALETA_STATUS.trocar.texto,
                fontSize: 12,
                fontWeight: 700,
              }}
              stroke={PALETA_STATUS.trocar.linha}
              strokeDasharray="3 3"
              x={instante}
            />
          ))}
          {marcador === undefined ? null : (
            <ReferenceLine stroke={PALETA_STATUS.ok.linha} x={marcador} />
          )}
          <Line
            activeDot={{ r: 6 }}
            dataKey="percentual"
            dot={{
              fill: PALETA_STATUS.ok.linha,
              r: 4,
              stroke: PALETA_STATUS.ok.texto,
              strokeWidth: 2,
            }}
            name="Cobertura"
            stroke={PALETA_STATUS.ok.linha}
            strokeWidth={3}
            type="linear"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export default memo(EvolucaoGrafico)
