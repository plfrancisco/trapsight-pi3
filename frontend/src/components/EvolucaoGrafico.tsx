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
export default function EvolucaoGrafico({
  serie,
  resumo,
  marcador,
}: EvolucaoGraficoProps) {
  const dominioInstante: [number | 'dataMin', number | 'dataMax'] =
    serie.length === 1
      ? [serie[0].instante - 60_000, serie[0].instante + 60_000]
      : ['dataMin', 'dataMax']

  return (
    <div
      aria-label={resumo}
      className="h-80 w-full rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
      role="img"
    >
      <ResponsiveContainer height="100%" width="100%">
        <LineChart data={serie} margin={{ top: 20, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid stroke="#E2E8F0" strokeDasharray="4 4" />
          <XAxis
            dataKey="instante"
            domain={dominioInstante}
            scale="time"
            tickFormatter={formatEixoData}
            tick={{ fill: '#334155', fontSize: 12 }}
            type="number"
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fill: '#334155', fontSize: 12 }}
            tickFormatter={(valor: number) => `${valor}%`}
          />
          <Tooltip
            formatter={(valor) => [formatPercentual(Number(valor)), 'Cobertura']}
            labelFormatter={(valor) => formatTooltipData(Number(valor))}
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
