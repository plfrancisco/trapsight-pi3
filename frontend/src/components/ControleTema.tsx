import type { Tema } from '../hooks/useTema'

interface ControleTemaProps {
  tema: Tema
  onAlternar: () => void
  compacto?: boolean
}

/** Oferece uma alternância explícita entre o tema claro e o escuro.
 * @param props Tema atual, ação e opção de ocultar o texto visual.
 * @returns Um controle acessível com ícone e rótulo para leitores de tela.
 */
export default function ControleTema({
  tema,
  onAlternar,
  compacto = false,
}: ControleTemaProps) {
  const proximoTema = tema === 'claro' ? 'escuro' : 'claro'
  const rotulo = proximoTema === 'escuro' ? 'Ativar tema escuro' : 'Ativar tema claro'

  return (
    <button
      aria-label={rotulo}
      className="theme-toggle"
      onClick={onAlternar}
      title={rotulo}
      type="button"
    >
      <svg aria-hidden="true" className="size-5" fill="none" viewBox="0 0 24 24">
        {tema === 'claro' ? (
          <>
            <path
              d="M20.2 15.2A8.2 8.2 0 0 1 8.8 3.8a8.2 8.2 0 1 0 11.4 11.4Z"
              stroke="currentColor"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="1.7"
            />
            <path d="M16.5 3v3m-1.5-1.5h3" stroke="currentColor" strokeLinecap="round" strokeWidth="1.5" />
          </>
        ) : (
          <>
            <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="1.7" />
            <path
              d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42"
              stroke="currentColor"
              strokeLinecap="round"
              strokeWidth="1.7"
            />
          </>
        )}
      </svg>
      <span className={compacto ? 'theme-toggle__label theme-toggle__label--desktop' : 'theme-toggle__label'}>
        {tema === 'claro' ? 'Tema escuro' : 'Tema claro'}
      </span>
    </button>
  )
}
