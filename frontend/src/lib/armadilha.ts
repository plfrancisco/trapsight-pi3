import { ApiError } from '../services/erros'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** Identifica erros da API que indicam que a armadilha solicitada não existe.
 * @param erro Falha recebida durante a consulta da armadilha.
 * @returns Se a API classificou a armadilha como ausente ou inválida como UUID.
 */
export function isArmadilhaAusente(erro: unknown): boolean {
  if (!(erro instanceof ApiError)) return false
  if (erro.codigo === 'ARMADILHA_NAO_ENCONTRADA') return true
  if (erro.codigo !== 'VALIDACAO_FALHOU') return false

  const detalhes: unknown = erro.detalhes
  if (!isRecord(detalhes)) return false

  const camposInvalidos = detalhes.campos_invalidos
  if (!Array.isArray(camposInvalidos)) return false

  return camposInvalidos.some(
    (campoInvalido: unknown) =>
      isRecord(campoInvalido) && campoInvalido.campo === 'armadilha_id',
  )
}
