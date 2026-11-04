interface MarcaTrapSightProps {
  variante?: 'automatica' | 'reversa'
}

/** Exibe o símbolo T com lente e o nome em duas cores da marca.
 * @param props Variante automática para superfícies de conteúdo ou reversa para a navegação escura.
 * @returns Assinatura visual vetorial do TrapSight.
 */
export default function MarcaTrapSight({ variante = 'automatica' }: MarcaTrapSightProps) {
  const classeVariante = variante === 'reversa' ? ' brand-lockup--reversed' : ''

  return (
    <span className={`brand-lockup${classeVariante}`}>
      <span aria-hidden="true" className="brand-mark">
        <svg className="brand-mark__symbol" fill="none" viewBox="0 0 120 120">
          <path
            className="brand-mark__body"
            d="M18 5h84a8 8 0 0 1 8 8v22a8 8 0 0 1-8 8H80v64a8 8 0 0 1-8 8H48a8 8 0 0 1-8-8V43H18a8 8 0 0 1-8-8V13a8 8 0 0 1 8-8Z"
          />
          {/* A lente cobre o encontro entre barra e haste para continuar legível no ícone de 32 px. */}
          <circle className="brand-mark__lens-halo" cx="60" cy="41" r="23" />
          <circle className="brand-mark__lens-ring" cx="60" cy="41" r="19" />
          <circle className="brand-mark__lens-center" cx="60" cy="41" r="12" />
        </svg>
      </span>
      <span aria-label="TrapSight" className="brand-wordmark" role="img">
        <span className="brand-wordmark__trap">Trap</span>
        <span className="brand-wordmark__sight">Sight</span>
      </span>
    </span>
  )
}
