/** Registra o service worker de produção depois que a página termina de carregar. */
export function registrarServiceWorker(): void {
  if (!import.meta.env.PROD || !('serviceWorker' in navigator)) return

  window.addEventListener(
    'load',
    () => {
      try {
        void navigator.serviceWorker
          .register('/sw.js', { scope: '/' })
          .catch(() => undefined)
      } catch {
        // Uma falha do navegador não pode interromper a aplicação.
      }
    },
    { once: true },
  )
}
