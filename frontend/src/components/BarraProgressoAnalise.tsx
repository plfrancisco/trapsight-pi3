import { useProgressoEstimado, type FaseProgresso } from '../hooks/useProgressoEstimado'

const TEXTO_FASE: Record<FaseProgresso, string> = {
  enviando: 'Enviando a foto…',
  medindo: 'O modelo está medindo a saturação…',
  concluida: 'Análise concluída',
}

interface BarraProgressoAnaliseProps {
  /** Verdadeiro quando a resposta da API chegou; a barra vai a 100%. */
  concluido: boolean
}

/** Mostra o andamento estimado de uma análise, que vai a 100% quando ela termina.
 *
 * O percentual é uma estimativa (a API não informa o andamento real). Monte o
 * componente somente enquanto a análise está em curso: ele conta o tempo desde que
 * aparece na tela.
 * @param props Indica se a análise já terminou.
 * @returns A barra, o percentual e a fase atual.
 */
export default function BarraProgressoAnalise({ concluido }: BarraProgressoAnaliseProps) {
  const { percentual, fase } = useProgressoEstimado(concluido)
  const arredondado = Math.round(percentual)
  const texto = TEXTO_FASE[fase]

  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between gap-3 text-sm font-medium text-emerald-950">
        <span>{texto}</span>
        <span aria-hidden="true" className="tabular-nums">
          {arredondado}%
        </span>
      </div>
      <div
        aria-label="Progresso da análise"
        aria-valuemax={100}
        aria-valuemin={0}
        aria-valuenow={arredondado}
        aria-valuetext={`${texto} ${arredondado}%`}
        className="h-3 w-full overflow-hidden rounded-full bg-emerald-100"
        role="progressbar"
      >
        <div
          className="h-full rounded-full bg-emerald-700 transition-[width] duration-300 ease-linear motion-reduce:transition-none"
          style={{ width: `${percentual}%` }}
        />
      </div>
      {/* Anuncia só a troca de fase (três vezes no máximo), não cada percentual. */}
      <p aria-live="polite" className="sr-only" role="status">
        {texto}
      </p>
    </div>
  )
}
