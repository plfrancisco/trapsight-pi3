import { request, TIMEOUT_UPLOAD_MS } from './http'
import type {
  ArmadilhaAtualizar,
  ArmadilhaCriar,
  ArmadilhaDetalhe,
  ArmadilhaLista,
  FotoArmadilhaSaida,
  RefilTrocaCriar,
  RefilTrocaSaida,
} from './tipos'

/** Lista armadilhas com o estado calculado pelo backend. */
export function listArmadilhas(signal?: AbortSignal): Promise<ArmadilhaLista[]> {
  return request<ArmadilhaLista[]>('armadilhas', { signal })
}

/** Cadastra uma armadilha, opcionalmente iniciando o primeiro ciclo de refil. */
export function createArmadilha(
  dados: ArmadilhaCriar,
  signal?: AbortSignal,
): Promise<ArmadilhaDetalhe> {
  return request<ArmadilhaDetalhe>('armadilhas', {
    method: 'POST',
    body: dados,
    signal,
  })
}

/** Consulta os dados e os ciclos de uma armadilha. */
export function getArmadilha(
  armadilhaId: string,
  signal?: AbortSignal,
): Promise<ArmadilhaDetalhe> {
  return request<ArmadilhaDetalhe>(
    'armadilhas/' + encodeURIComponent(armadilhaId),
    { signal },
  )
}

/** Atualiza os campos editáveis de uma armadilha. */
export function updateArmadilha(
  armadilhaId: string,
  dados: ArmadilhaAtualizar,
  signal?: AbortSignal,
): Promise<ArmadilhaDetalhe> {
  return request<ArmadilhaDetalhe>(
    'armadilhas/' + encodeURIComponent(armadilhaId),
    {
      method: 'PATCH',
      body: dados,
      signal,
    },
  )
}

/** Remove a armadilha do painel e preserva seu histórico no banco. */
export function deleteArmadilha(
  armadilhaId: string,
  signal?: AbortSignal,
): Promise<void> {
  return request<void>(
    'armadilhas/' + encodeURIComponent(armadilhaId),
    { method: 'DELETE', signal },
  )
}

/** Encerra o ciclo ativo e registra o novo refil em uma única operação da API. */
export function replaceRefil(
  armadilhaId: string,
  dados: RefilTrocaCriar,
  signal?: AbortSignal,
): Promise<RefilTrocaSaida> {
  return request<RefilTrocaSaida>(
    'armadilhas/' + encodeURIComponent(armadilhaId) + '/refis',
    { method: 'POST', body: dados, signal },
  )
}

/** Envia a foto real da armadilha; o servidor reduz a imagem e remove os metadados. */
export function sendFotoArmadilha(
  armadilhaId: string,
  arquivo: File,
  signal?: AbortSignal,
): Promise<FotoArmadilhaSaida> {
  const dados = new FormData()
  dados.append('arquivo', arquivo)
  return request<FotoArmadilhaSaida>(
    'armadilhas/' + encodeURIComponent(armadilhaId) + '/foto',
    { method: 'PUT', body: dados, signal, timeoutMs: TIMEOUT_UPLOAD_MS },
  )
}

/** Volta a armadilha à foto padrão do modelo; repetir a chamada não causa erro. */
export function deleteFotoArmadilha(
  armadilhaId: string,
  signal?: AbortSignal,
): Promise<void> {
  return request<void>(
    'armadilhas/' + encodeURIComponent(armadilhaId) + '/foto',
    { method: 'DELETE', signal },
  )
}
