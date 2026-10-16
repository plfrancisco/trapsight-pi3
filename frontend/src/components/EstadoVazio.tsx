import type { ReactNode } from 'react'

interface EstadoVazioProps {
  titulo: string
  descricao: string
  acao?: ReactNode
}

/** Explica a ausência de conteúdo e permite oferecer uma ação contextual. */
export default function EstadoVazio({
  titulo,
  descricao,
  acao,
}: EstadoVazioProps) {
  return (
    <section className="rounded-2xl border border-dashed border-slate-300 bg-white px-5 py-8 sm:px-8">
      <h2 className="text-lg font-semibold tracking-tight text-slate-950">
        {titulo}
      </h2>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-700">
        {descricao}
      </p>
      {acao ? <div className="mt-5">{acao}</div> : null}
    </section>
  )
}
