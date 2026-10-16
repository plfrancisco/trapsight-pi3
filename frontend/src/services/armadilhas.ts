import { request } from './http'
import type {
  ArmadilhaAtualizar,
  ArmadilhaCriar,
  ArmadilhaDetalhe,
  ArmadilhaLista,
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
