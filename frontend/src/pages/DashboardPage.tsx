import { useCallback } from 'react'
import Botao from '../components/Botao'
import CartaoArmadilha from '../components/CartaoArmadilha'
import LinkBotao from '../components/LinkBotao'
import MensagemErro from '../components/MensagemErro'
import PainelAlertas from '../components/PainelAlertas'
import { useCarregamento } from '../hooks/useCarregamento'
import { ApiError } from '../services/erros'
import { listArmadilhas } from '../services/armadilhas'

interface IndicadorProps {
  label: string
  valor: string | number
  detalhe: string
  tipo: 'total' | 'atencao' | 'trocar'
}

/** Exibe uma métrica real da consulta sem acrescentar tendências presumidas.
 * @param props Rótulo, valor, descrição e tom semântico.
 * @returns Um indicador compacto para a visão geral.
 */
function Indicador({ label, valor, detalhe, tipo }: IndicadorProps) {
  return (
    <div className={`metric-card metric-card--${tipo}`}>
      <dt className="metric-card__label">{label}</dt>
      <dd className="metric-card__value">{valor}</dd>
      <p className="metric-card__detail">{detalhe}</p>
    </div>
  )
}

/** Apresenta alertas, indicadores e cartões de todas as armadilhas monitoradas.
 * @returns A tela inicial com estados de carregamento, erro e lista operacional.
 */
export default function DashboardPage() {
  const loadArmadilhas = useCallback(
    (signal: AbortSignal) => listArmadilhas(signal),
    [],
  )
  const {
    dados,
    erro,
    carregando,
    recarregar: reload,
  } = useCarregamento(loadArmadilhas)

  const totalArmadilhas = dados?.length ?? 0
  const totalAtencao = dados?.filter((armadilha) => armadilha.status === 'atencao').length ?? 0
  const totalTroca = dados?.filter((armadilha) => armadilha.status === 'trocar').length ?? 0
  const valorIndicador = dados === null || carregando || erro ? '—' : undefined

  return (
    <div className="dashboard-page page-stack">
      <header className="dashboard-hero">
        <div className="dashboard-hero__copy">
          <div className="dashboard-hero__intro">
          <p className="page-kicker">Monitoramento de armadilhas</p>
          <h1 className="dashboard-hero__title">Dashboard</h1>
          <p className="dashboard-hero__description">
            Veja as leituras recentes, identifique o que pede atenção e planeje as trocas.
          </p>
          </div>
          <div className="dashboard-hero__actions">
            <LinkBotao to="/analises/nova" variante="primario">
              Iniciar análise
              <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24">
                <path d="M5 12h14m-6-6 6 6-6 6" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
              </svg>
            </LinkBotao>
            <LinkBotao to="/armadilhas/nova" variante="secundario">
              Cadastrar armadilha
            </LinkBotao>
          </div>
        </div>

      </header>

      <dl aria-label="Resumo das armadilhas" className="metric-grid">
        <Indicador
          detalhe="em acompanhamento"
          label="Armadilhas"
          tipo="total"
          valor={valorIndicador ?? totalArmadilhas}
        />
        <Indicador
          detalhe="pedem uma verificação"
          label="Em atenção"
          tipo="atencao"
          valor={valorIndicador ?? totalAtencao}
        />
        <Indicador
          detalhe="trocas recomendadas"
          label="Precisam de troca"
          tipo="trocar"
          valor={valorIndicador ?? totalTroca}
        />
      </dl>

      <PainelAlertas
        armadilhas={dados}
        carregando={carregando}
        erro={Boolean(erro)}
        instanteReferencia={new Date()}
      />

      <section aria-labelledby="titulo-armadilhas" className="dashboard-section">
        <div className="section-heading">
          <div>

            <h2 className="section-title" id="titulo-armadilhas">
              Armadilhas monitoradas
            </h2>

          </div>
          {dados !== null && !erro && !carregando ? (
            <span className="section-count">
              {dados.length === 1
                ? '1 armadilha cadastrada'
                : `${dados.length} armadilhas cadastradas`}
            </span>
          ) : null}
        </div>

        {carregando ? (
          <p className="loading-panel" role="status">
            Carregando armadilhas…
          </p>
        ) : null}
        {erro ? (
          <div className="state-panel state-panel--error">
            <MensagemErro
              erro={
                erro instanceof ApiError
                  ? erro
                  : 'Não foi possível carregar as armadilhas.'
              }
            />
            <Botao onClick={reload} variante="primario">
              Tentar novamente
            </Botao>
          </div>
        ) : null}
        {!carregando && !erro && dados?.length === 0 ? (
          <section aria-labelledby="titulo-vazio" className="empty-state-panel">
            <span aria-hidden="true" className="empty-state-panel__mark">
              <svg className="size-7" fill="none" viewBox="0 0 28 28">
                <rect height="20" rx="5" stroke="currentColor" strokeWidth="1.7" width="20" x="4" y="4" />
                <path d="M9 8v12M14 8v12M19 8v12M7 11h14M7 16h14" stroke="currentColor" strokeLinecap="round" strokeWidth="1.25" />
              </svg>
            </span>
            <h3 className="section-title" id="titulo-vazio">
              Nenhuma armadilha cadastrada
            </h3>
            <p className="section-description">
              Cadastre a primeira armadilha para começar a acompanhar as leituras e os refis.
            </p>
            <LinkBotao to="/armadilhas/nova" variante="primario">
              Cadastrar primeira armadilha
            </LinkBotao>
          </section>
        ) : null}
        {!carregando && !erro && dados && dados.length > 0 ? (
          <ul className="trap-grid">
            {dados.map((armadilha) => (
              <li key={armadilha.id}>
                <CartaoArmadilha armadilha={armadilha} />
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </div>
  )
}
