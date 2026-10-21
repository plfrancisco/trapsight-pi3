/** Identidade visual do produto: o selo "TS" e o nome.
 * @returns O selo e o nome, para uso dentro de um link ou de um título.
 */
export default function MarcaTrapSight() {
  return (
    <>
      <span
        aria-hidden="true"
        className="inline-flex size-9 items-center justify-center rounded-xl bg-emerald-900 text-sm font-bold text-white"
      >
        TS
      </span>
      TrapSight
    </>
  )
}
