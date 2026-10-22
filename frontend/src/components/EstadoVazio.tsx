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
    <section className="empty-state-panel">
      <span aria-hidden="true" className="empty-state-panel__mark">
        <svg className="size-7" fill="none" viewBox="0 0 28 28">
          <rect height="20" rx="5" stroke="currentColor" strokeWidth="1.7" width="20" x="4" y="4" />
          <path d="M9 8v12M14 8v12M19 8v12M7 11h14M7 16h14" stroke="currentColor" strokeLinecap="round" strokeWidth="1.25" />
        </svg>
      </span>
      <h2 className="section-title">
        {titulo}
      </h2>
      <p className="section-description">
        {descricao}
      </p>
      {acao ? <div className="mt-5">{acao}</div> : null}
    </section>
  )
}
