import { useCallback } from 'react'
import { useParams } from 'react-router'
import ArmadilhaNaoEncontrada from '../components/ArmadilhaNaoEncontrada'
import Botao from '../components/Botao'
import EstadoCarregando from '../components/EstadoCarregando'
import EstadoVazio from '../components/EstadoVazio'
import ListaAnalises from '../components/ListaAnalises'
import ListaRefisAnteriores from '../components/ListaRefisAnteriores'
import LinkBotao from '../components/LinkBotao'
import MensagemErro from '../components/MensagemErro'
import ResumoArmadilha from '../components/ResumoArmadilha'
import ResumoRefil from '../components/ResumoRefil'
import EvolucaoCobertura from '../components/EvolucaoCobertura'
import TrocaRefil from '../components/TrocaRefil'
import { useCarregamento } from '../hooks/useCarregamento'
import { isArmadilhaAusente } from '../lib/armadilha'
import { ApiError } from '../services/erros'
import { listAnalises } from '../services/analises'
import { getArmadilha } from '../services/armadilhas'

/** Carrega e apresenta o estado atual e o histórico do ciclo ativo.
 * @returns Detalhe da armadilha, estados de consulta, série e ações de refil.
 */
export default function DetalheArmadilhaPage() {
  const armadilhaId = useParams().id ?? ''
  const carregarDetalhe = useCallback(
    async (signal: AbortSignal) => {
      const armadilha = await getArmadilha(armadilhaId, signal)
      const analises = await listAnalises(
        armadilhaId,
        {
          escopo: armadilha.removida_em ? 'completo' : 'refil_ativo',
          limite: 1000,
        },
        signal,
      )
      return { armadilha, analises }
    },
    [armadilhaId],
  )
  const { dados, erro, carregando, recarregar } = useCarregamento(carregarDetalhe)

  if (dados === null && carregando) {
    return (
      <div className="space-y-4">
        <h1 className="text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">
          Detalhe da armadilha
        </h1>
        <EstadoCarregando />
      </div>
    )
  }
  if (dados === null && isArmadilhaAusente(erro)) {
    return <ArmadilhaNaoEncontrada />
  }
  if (dados === null && erro) {
    return (
      <div className="space-y-4">
        <MensagemErro erro={erro instanceof ApiError ? erro : 'Não foi possível carregar a armadilha.'} />
        <Botao onClick={recarregar} variante="primario">
          Tentar novamente
        </Botao>
      </div>
    )
  }
  if (dados === null) return null

  const { armadilha, analises } = dados

  return (
    <div className="space-y-8">
      <ResumoArmadilha armadilha={armadilha} />
      {erro ? (
        <div className="space-y-3">
          <MensagemErro erro={erro instanceof ApiError ? erro : 'Não foi possível atualizar os dados.'} />
          <Botao onClick={recarregar} variante="primario">
            Tentar novamente
          </Botao>
        </div>
      ) : null}
      <div className="grid gap-4 lg:grid-cols-2">
        <ResumoRefil
          diasAteSaturar={armadilha.dias_ate_saturar}
          percentualAtual={armadilha.percentual_atual}
          refil={armadilha.refil_ativo}
          status={armadilha.status}
        />
        <ListaRefisAnteriores refis={armadilha.refis_anteriores} />
      </div>
      {!armadilha.removida_em ? (
        <TrocaRefil
          onConcluir={recarregar}
          armadilhaId={armadilha.id}
          temRefilAtivo={armadilha.refil_ativo !== null}
        />
      ) : null}
      {analises.length === 0 ? (
        <section aria-labelledby="titulo-evolucao">
          <div className="mb-4">
            <p className="text-sm font-semibold uppercase tracking-wide text-slate-600">
              Refil ativo
            </p>
            <h2
              className="mt-1 text-2xl font-semibold tracking-tight text-slate-950"
              id="titulo-evolucao"
            >
              Evolução da cobertura
            </h2>
          </div>
          <EstadoVazio
            acao={armadilha.removida_em ? undefined : (
              <LinkBotao to="/analises/nova" variante="primario">
                Enviar a primeira imagem
              </LinkBotao>
            )}
            descricao={armadilha.removida_em
              ? 'Esta armadilha não possui análises registradas.'
              : 'Envie uma imagem para iniciar o histórico de cobertura deste ciclo.'}
            titulo={armadilha.removida_em ? 'Nenhuma análise no histórico' : 'Nenhuma análise neste refil'}
          />
        </section>
      ) : !armadilha.removida_em ? (
        <EvolucaoCobertura
          key={armadilha.id}
          analisesAtivas={analises}
          diasAteSaturar={armadilha.dias_ate_saturar}
          limiarTrocar={armadilha.limiar_trocar}
        />
      ) : null}
      <ListaAnalises
        analises={analises}
        historicoCompleto={Boolean(armadilha.removida_em)}
      />
    </div>
  )
}
