/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string
  readonly VITE_AUTENTICACAO_ATIVA?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
