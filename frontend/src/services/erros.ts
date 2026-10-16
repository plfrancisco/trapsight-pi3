/** Códigos criados no cliente quando a resposta não fornece um envelope confiável da API. */
export type CodigoErroCliente =
  | 'FALHA_DE_REDE'
  | 'TEMPO_ESGOTADO'
  | 'RESPOSTA_INVALIDA'

/** Normaliza erros da API e de transporte sem depender do texto para classificá-los. */
export class ApiError extends Error {
  readonly codigo: string
  readonly mensagem: string
  readonly status: number
  readonly detalhes?: Record<string, unknown>

  /** Cria um erro com o código estável, a mensagem pública e o status HTTP. */
  constructor(codigo: string, mensagem: string, status: number, detalhes?: Record<string, unknown>) {
    super(mensagem)
    this.name = 'ApiError'
    this.codigo = codigo
    this.mensagem = mensagem
    this.status = status
    this.detalhes = detalhes
  }
}
