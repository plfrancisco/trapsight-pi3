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
      <label className="block text-sm font-semibold text-slate-900" htmlFor={id}>
        {rotulo}
        {obrigatorio ? <span aria-hidden="true"> *</span> : null}
      </label>
      <input
        aria-describedby={descricoes || undefined}
        aria-invalid={erro ? true : undefined}
        autoComplete={autoComplete}
        className="min-h-12 w-full rounded-xl border border-slate-300 bg-white px-3.5 py-3 text-base text-slate-950 shadow-sm placeholder:text-slate-500 focus-visible:border-emerald-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-800 read-only:bg-slate-100"
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
        <p className="text-sm leading-5 text-slate-700" id={`${id}-ajuda`}>
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
