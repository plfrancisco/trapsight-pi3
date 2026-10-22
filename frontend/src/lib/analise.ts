import { ApiError } from '../services/erros'
import type { ArmadilhaLista } from '../services/tipos'

const TAMANHO_MAXIMO_ARQUIVO = 4 * 1024 * 1024

const MENSAGENS_POR_CODIGO: Record<string, string> = {
  ARQUIVO_MUITO_GRANDE: 'A imagem excede o limite de 4 MB.',
  FORMATO_NAO_SUPORTADO: 'Envie uma imagem JPEG ou PNG.',
  RESOLUCAO_INSUFICIENTE:
    'A imagem precisa ter pelo menos 512 px no maior lado.',
  REFIL_ATIVO_INEXISTENTE:
    'Esta armadilha não tem refil ativo. Registre um refil antes de enviar a análise.',
  PLACA_NAO_DETECTADA:
    'Não foi possível detectar a superfície adesiva na imagem.',
  FALHA_INFERENCIA:
    'A análise não pôde ser concluída. Tente novamente mais tarde.',
  FALHA_DE_REDE:
    'Não foi possível conectar à API. Verifique a conexão e tente novamente.',
  TEMPO_ESGOTADO: 'A análise excedeu o tempo limite. Tente novamente.',
}

/** Valida extensão, tipo declarado e tamanho sem substituir as verificações da API.
 * @param arquivo Arquivo escolhido no navegador.
 * @returns Mensagem de validação ou null quando o arquivo pode ser enviado.
 */
export function validateArquivoAnalise(
  arquivo: Pick<File, 'name' | 'type' | 'size'>,
): string | null {
  const extensao = arquivo.name.split('.').pop()?.toLowerCase()
  const jpegValido =
    arquivo.type === 'image/jpeg' &&
    (extensao === 'jpg' || extensao === 'jpeg')
  const pngValido = arquivo.type === 'image/png' && extensao === 'png'

  if (!jpegValido && !pngValido) {
    return 'Selecione um arquivo JPEG (.jpg ou .jpeg) ou PNG (.png).'
  }
  if (arquivo.size > TAMANHO_MAXIMO_ARQUIVO) {
    return 'O arquivo deve ter no máximo 4 MB.'
  }
  return null
}

/** Traduz erros estáveis da API e preserva a mensagem para códigos desconhecidos.
 * @param codigo Código recebido no envelope de erro.
 * @param mensagem Mensagem genérica fornecida pela API.
 * @returns Texto claro em português para a tela de análise.
 */
export function buildMensagemErroAnalise(
  codigo: string,
  mensagem: string,
): string {
  return MENSAGENS_POR_CODIGO[codigo] ?? mensagem
}

/** Identifica cancelamentos padronizados pelo navegador.
 * @param erro Valor recebido ao rejeitar uma operação assíncrona.
 * @returns True quando a rejeição representa cancelamento.
 */
export function isAbortError(erro: unknown): boolean {
  return (
    typeof erro === 'object' &&
    erro !== null &&
    'name' in erro &&
    erro.name === 'AbortError'
  )
}

/** Converte falhas de análise em mensagens apropriadas para exibição.
 * @param erro Falha retornada pela API ou por outra etapa do envio.
 * @returns Mensagem segura e clara para a interface.
 */
export function buildFalhaMensagem(erro: unknown): string {
  if (erro instanceof ApiError) {
    return buildMensagemErroAnalise(erro.codigo, erro.mensagem)
  }
  return 'Não foi possível concluir a análise. Tente novamente.'
}

/** Localiza uma armadilha pelo identificador sem alterar a lista recebida.
 * @param armadilhas Lista carregada ou nula enquanto a consulta não termina.
 * @param armadilhaId Identificador da armadilha selecionada.
 * @returns A armadilha encontrada ou null quando não há correspondência.
 */
export function findArmadilha(
  armadilhas: ArmadilhaLista[] | null,
  armadilhaId: string,
): ArmadilhaLista | null {
  return armadilhas?.find((armadilha) => armadilha.id === armadilhaId) ?? null
}
