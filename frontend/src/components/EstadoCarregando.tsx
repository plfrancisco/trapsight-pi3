/** Informa que o conteúdo solicitado ainda está sendo carregado. */
export default function EstadoCarregando() {
  return (
    <div
      aria-live="polite"
      className="flex min-h-12 items-center gap-3 text-sm font-medium text-slate-700"
      role="status"
    >
      <span
        aria-hidden="true"
        className="size-5 animate-spin rounded-full border-2 border-emerald-800 border-r-transparent"
      />
      Carregando…
    </div>
  )
}
