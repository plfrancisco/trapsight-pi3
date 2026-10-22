import { useId, type ChangeEvent } from 'react'
import { limitarVelocidade, VELOCIDADE_MAX_MS, VELOCIDADE_MIN_MS } from '../lib/timelapse'
import Botao from './Botao'

export type EscopoTimelapse = 'refil_ativo' | 'completo'

interface ControlesTimelapseProps {
  escopo: EscopoTimelapse
  indiceQuadro: number
  quantidade: number
  reproduzindo: boolean
  velocidadeMs: number
  onChangeEscopo: (escopo: EscopoTimelapse) => void
  onChangeQuadro: (indice: number) => void
  onChangeVelocidade: (velocidadeMs: number) => void
  onTogglePlayback: () => void
}

/** Apresenta seleção de período, reprodução, velocidade e navegação manual.
 * @param props Escopo e estado atuais com as ações das interações do usuário.
 * @returns Controles acessíveis para inspecionar o timelapse.
 */
export default function ControlesTimelapse({
  escopo,
  indiceQuadro,
  quantidade,
  reproduzindo,
  velocidadeMs,
  onChangeEscopo,
  onChangeQuadro,
  onChangeVelocidade,
  onTogglePlayback,
}: ControlesTimelapseProps) {
  const idControleQuadro = useId()
  const idControleVelocidade = useId()

  function changeVelocidade(event: ChangeEvent<HTMLInputElement>) {
    onChangeVelocidade(limitarVelocidade(Number(event.currentTarget.value)))
  }

  return (
    <div className="surface-panel space-y-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
      <fieldset>
        <legend className="text-sm font-semibold text-slate-950">Escopo temporal</legend>
        <div className="mt-2 flex flex-wrap gap-x-5 gap-y-2">
          <label className="inline-flex min-h-11 items-center gap-2 text-sm text-slate-800">
            <input
              checked={escopo === 'refil_ativo'}
              className="size-4 accent-emerald-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-800"
              name="escopo-timelapse"
              onChange={() => onChangeEscopo('refil_ativo')}
              type="radio"
              value="refil_ativo"
            />
            Refil ativo
          </label>
          <label className="inline-flex min-h-11 items-center gap-2 text-sm text-slate-800">
            <input
              checked={escopo === 'completo'}
              className="size-4 accent-emerald-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-800"
              name="escopo-timelapse"
              onChange={() => onChangeEscopo('completo')}
              type="radio"
              value="completo"
            />
            Histórico completo
          </label>
        </div>
      </fieldset>

      {quantidade < 2 ? null : (
        <div className="space-y-4 border-t border-slate-200 pt-4">
          <Botao
            aria-pressed={reproduzindo}
            onClick={onTogglePlayback}
            variante="primario"
          >
            {reproduzindo ? 'Pausar' : 'Reproduzir'}
          </Botao>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label
                className="block text-sm font-semibold text-slate-900"
                htmlFor={idControleQuadro}
              >
                Quadro atual: {indiceQuadro + 1} de {quantidade}
              </label>
              <input
                aria-valuetext={`Quadro ${indiceQuadro + 1} de ${quantidade}`}
                className="mt-2 min-h-11 w-full accent-emerald-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-800"
                id={idControleQuadro}
                max={quantidade - 1}
                min={0}
                onChange={(event) => onChangeQuadro(Number(event.currentTarget.value))}
                step={1}
                type="range"
                value={indiceQuadro}
              />
            </div>
            <div>
              <label
                className="block text-sm font-semibold text-slate-900"
                htmlFor={idControleVelocidade}
              >
                Velocidade: {velocidadeMs} ms por quadro
              </label>
              <input
                aria-valuetext={`${velocidadeMs} ms por quadro`}
                className="mt-2 min-h-11 w-full accent-emerald-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-800"
                id={idControleVelocidade}
                max={VELOCIDADE_MAX_MS}
                min={VELOCIDADE_MIN_MS}
                onChange={changeVelocidade}
                step={100}
                type="range"
                value={velocidadeMs}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
