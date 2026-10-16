import { lazy, Suspense, useCallback } from 'react'
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
import TrocaRefil from '../components/TrocaRefil'
import { useCarregamento } from '../hooks/useCarregamento'
import { isArmadilhaAusente } from '../lib/armadilha'
import { buildResumoCobertura, buildSerieCobertura } from '../lib/cobertura'
import { ApiError } from '../services/erros'
import { listAnalises } from '../services/analises'
import { getArmadilha } from '../services/armadilhas'

const EvolucaoGrafico = lazy(() => import('../components/EvolucaoGrafico'))

/** Carrega e apresenta o estado atual e o histórico do ciclo ativo.
 * @returns Detalhe da armadilha, estados de consulta, série e ações de refil.
 */
export default function DetalheArmadilhaPage() {
  const armadilhaId = useParams().id ?? ''
  const carregarDetalhe = useCallback(
    (signal: AbortSignal) =>
      Promise.all([
        getArmadilha(armadilhaId, signal),
        listAnalises(armadilhaId, { escopo: 'refil_ativo', limite: 1000 }, signal),
      ]).then(([armadilha, analises]) => ({ armadilha, analises })),
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
  const serie = buildSerieCobertura(analises)
  const resumo = buildResumoCobertura(analises)

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
      <TrocaRefil
        onConcluir={recarregar}
        armadilhaId={armadilha.id}
        temRefilAtivo={armadilha.refil_ativo !== null}
      />
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
        {analises.length === 0 ? (
          <EstadoVazio
            acao={
              <LinkBotao to="/analises/nova" variante="primario">
                Enviar a primeira imagem
              </LinkBotao>
            }
            descricao="Envie uma imagem para iniciar o histórico de cobertura deste ciclo."
            titulo="Nenhuma análise neste refil"
          />
        ) : (
          <Suspense fallback={<div aria-live="polite" className="h-80" role="status">Carregando gráfico…</div>}>
            <EvolucaoGrafico resumo={resumo} serie={serie} />
          </Suspense>
        )}
      </section>
      <ListaAnalises analises={analises} />
    </div>
  )
}
