/** Identidade visual do produto, com um símbolo que remete à malha da armadilha.
 * @returns O selo vetorial e o nome TrapSight.
 */
export default function MarcaTrapSight() {
  return (
    <>
      <span aria-hidden="true" className="brand-mark">
        <svg className="size-6" fill="none" viewBox="0 0 28 28">
          <rect height="20" rx="5" stroke="currentColor" strokeWidth="1.7" width="20" x="4" y="4" />
          <path d="M9 8v12M14 8v12M19 8v12M7 11h14M7 16h14" stroke="currentColor" strokeLinecap="round" strokeWidth="1.25" />
          <circle cx="14" cy="13.5" fill="currentColor" r="1.5" />
        </svg>
      </span>
      <span className="brand-wordmark">TrapSight</span>
    </>
  )
}
