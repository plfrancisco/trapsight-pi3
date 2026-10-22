import type { ChangeEventHandler, Ref } from 'react'

interface CampoFormularioProps {
  id: string
  nome: string
  rotulo: string
  tipo?: 'text' | 'date' | 'email' | 'password'
  /** Sugestão de preenchimento do navegador e dos gerenciadores de senha. */
  autoComplete?: string
  valorPadrao?: string
  obrigatorio?: boolean
  somenteLeitura?: boolean
  descricao?: string
  erro?: string | null
  referencia?: Ref<HTMLInputElement>
  onChange?: ChangeEventHandler<HTMLInputElement>
}

/** Associa cada campo de formulário ao seu rótulo, ajuda e mensagem de erro. */
export default function CampoFormulario({
  id,
  nome,
  rotulo,
  tipo = 'text',
  autoComplete,
  valorPadrao,
  obrigatorio = false,
  somenteLeitura = false,
  descricao,
  erro,
  referencia,
  onChange,
}: CampoFormularioProps) {
  const descricoes = [
    descricao ? `${id}-ajuda` : null,
    erro ? `${id}-erro` : null,
  ]
    .filter((valor): valor is string => valor !== null)
    .join(' ')

  return (
    <div className="space-y-2">
      <label className="block text-sm font-semibold text-app-foreground" htmlFor={id}>
        {rotulo}
        {obrigatorio ? <span aria-hidden="true"> *</span> : null}
      </label>
      <input
        aria-describedby={descricoes || undefined}
        aria-invalid={erro ? true : undefined}
        autoComplete={autoComplete}
        className="min-h-12 w-full rounded-[14px] border border-app-border bg-app-surface px-3.5 py-3 text-base text-app-foreground shadow-[var(--app-shadow-control)] placeholder:text-app-muted focus-visible:border-app-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-primary read-only:bg-app-soft"
        defaultValue={somenteLeitura ? undefined : valorPadrao}
        id={id}
        name={nome}
        onChange={onChange}
        readOnly={somenteLeitura}
        ref={referencia}
        required={obrigatorio}
        type={tipo}
        value={somenteLeitura ? valorPadrao ?? '' : undefined}
      />
      {descricao ? (
        <p className="text-sm leading-5 text-app-muted" id={`${id}-ajuda`}>
          {descricao}
        </p>
      ) : null}
      {erro ? (
        <p className="text-sm font-medium text-red-800" id={`${id}-erro`}>
          {erro}
        </p>
      ) : null}
    </div>
  )
}
