import { useEffect, useState } from 'react'

/** Informa quando o navegador está sem rede, sem sugerir envio offline. */
export default function AvisoSemConexao() {
  const [offline, setOffline] = useState(() => !navigator.onLine)

  useEffect(() => {
    const atualizarConexao = () => setOffline(!navigator.onLine)
    window.addEventListener('online', atualizarConexao)
    window.addEventListener('offline', atualizarConexao)

    return () => {
      window.removeEventListener('online', atualizarConexao)
      window.removeEventListener('offline', atualizarConexao)
    }
  }, [])

  if (!offline) return null

  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed inset-x-0 top-0 z-[100] flex justify-center px-4 pt-[calc(env(safe-area-inset-top)+0.75rem)]"
      role="status"
    >
      <p className="max-w-xl rounded-xl border border-app-border bg-app-surface px-4 py-3 text-center text-sm font-semibold text-app-foreground shadow-lg">
        Sem conexão. A análise precisa de internet.
      </p>
    </div>
  )
}
