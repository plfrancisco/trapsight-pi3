/** Identidade visual do produto, com um símbolo que remete à malha da armadilha.
 * @returns O selo vetorial e o nome TrapSight.
 */
export default function MarcaTrapSight() {
  return (
    <>
      <span aria-hidden="true" className="brand-mark">
        <svg className="size-6" fill="none" viewBox="0 0 28 28">
          <path d="M9 4.5H6.5a2 2 0 0 0-2 2V9M19 4.5h2.5a2 2 0 0 1 2 2V9M23.5 19v2.5a2 2 0 0 1-2 2H19M9 23.5H6.5a2 2 0 0 1-2-2V19" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
          <path d="M14 7v2.4m0 9.2V21m-7-7h2.4m9.2 0H21" stroke="currentColor" strokeLinecap="round" strokeWidth="1.25" />
          <circle cx="14" cy="14" r="4.5" stroke="currentColor" strokeWidth="1.35" />
          <circle cx="14" cy="14" r="1.55" fill="currentColor" />
        </svg>
      </span>
      <span className="brand-wordmark">TrapSight</span>
    </>
  )
}
