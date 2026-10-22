import { useRef, useState, type KeyboardEvent } from 'react'
import type { ModeloArmadilha } from '../services/tipos'
import { imagemDoModelo } from '../lib/modeloImagem'

interface SeletorModeloProps {
  modelos: ModeloArmadilha[]
  valorPadrao: string | null
  erro?: string | null
  onChange?: () => void
}

/** Escolhe um modelo num menu compacto com miniaturas de referência. */
export default function SeletorModelo({
  modelos,
  valorPadrao,
  erro,
  onChange,
}: SeletorModeloProps) {
  const [selecionado, setSelecionado] = useState(valorPadrao)
  const detalhesRef = useRef<HTMLDetailsElement>(null)
  const resumoRef = useRef<HTMLElement>(null)
  const modeloSelecionado = modelos.find((modelo) => modelo.id === selecionado)

  function escolherModelo(modeloId: string) {
    setSelecionado(modeloId)
    onChange?.()
    if (detalhesRef.current) detalhesRef.current.open = false
    resumoRef.current?.focus()
  }

  function fecharComEscape(evento: KeyboardEvent<HTMLDetailsElement>) {
    if (evento.key !== 'Escape' || !detalhesRef.current?.open) return
    evento.preventDefault()
    detalhesRef.current.open = false
    resumoRef.current?.focus()
  }

  return (
    <div className="space-y-2">
      <label className="block text-sm font-semibold text-app-foreground" id="modelo-label">
        Modelo da armadilha <span aria-hidden="true">*</span>
      </label>
      <input name="modelo_id" type="hidden" value={selecionado ?? ''} />
      <details
        className="model-picker"
        onKeyDown={fecharComEscape}
        ref={detalhesRef}
      >
        <summary
          aria-describedby={erro ? 'modelo-erro' : undefined}
          aria-labelledby="modelo-label modelo-valor"
          className="model-picker__trigger"
          ref={resumoRef}
        >
          {modeloSelecionado ? (
            <>
              <ModeloThumb modelo={modeloSelecionado} />
              <span className="model-picker__selected-name" id="modelo-valor">{modeloSelecionado.nome}</span>
            </>
          ) : (
            <span className="model-picker__placeholder" id="modelo-valor">Selecione um modelo</span>
          )}
          <svg aria-hidden="true" className="model-picker__chevron" viewBox="0 0 20 20">
            <path d="m5 7.5 5 5 5-5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
          </svg>
        </summary>
        <div aria-label="Modelos disponíveis" className="model-picker__menu" role="group">
          {modelos.map((modelo) => (
            <button
              aria-pressed={modelo.id === selecionado}
              className="model-picker__option"
              key={modelo.id}
              onClick={() => escolherModelo(modelo.id)}
              type="button"
            >
              <ModeloThumb modelo={modelo} />
              <span className="model-picker__option-name">{modelo.nome}</span>
              {modelo.id === selecionado ? (
                <svg aria-label="Selecionado" className="model-picker__check" viewBox="0 0 20 20">
                  <path d="m4 10 4 4 8-8" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
                </svg>
              ) : null}
            </button>
          ))}
        </div>
      </details>
      {erro ? (
        <p className="text-sm font-medium text-red-800" id="modelo-erro" role="alert">
          {erro}
        </p>
      ) : null}
    </div>
  )
}

function ModeloThumb({ modelo }: { modelo: ModeloArmadilha }) {
  const imagem = imagemDoModelo(modelo.codigo)
  return imagem ? (
    <img
      alt=""
      className="model-picker__thumb"
      decoding="async"
      loading="lazy"
      src={imagem}
    />
  ) : (
    <span aria-hidden="true" className="model-picker__thumb model-picker__thumb--empty">
      {modelo.nome.slice(0, 1)}
    </span>
  )
}
