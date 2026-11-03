/** Identidade visual do produto, com um símbolo que remete à malha da armadilha.
 * @returns O selo vetorial e o nome TrapSight.
 */
export default function MarcaTrapSight() {
  return (
    <>
      <span aria-hidden="true" className="brand-mark">
        <svg className="size-6" fill="none" viewBox="0 0 28 28">
          <path d="M9 4.5H6.5a2 2 0 0 0-2 2V9M19 4.5h2.5a2 2 0 0 1 2 2V9M23.5 19v2.5a2 2 0 0 1-2 2H19M9 23.5H6.5a2 2 0 0 1-2-2V19" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
          <rect height="11" rx="1.25" stroke="currentColor" strokeWidth="1.15" width="11" x="8.5" y="8.5" />
          <path d="M12.17 8.5v11m3.66-11v11M8.5 12.17h11m-11 3.66h11" stroke="currentColor" strokeOpacity=".76" strokeWidth=".75" />
          <circle cx="15.83" cy="12.17" r="2.1" fill="var(--brand-point)" stroke="currentColor" strokeWidth=".85" />
        </svg>
      </span>
      <span className="brand-wordmark">TrapSight</span>
    </>
  )
}
