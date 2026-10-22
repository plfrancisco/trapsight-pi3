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
      <div className="metric-card__topline">
        <span className="metric-card__label">{label}</span>
        <span aria-hidden="true" className="metric-card__icon">
          {tipo === 'total' ? (
            <svg className="size-5" fill="none" viewBox="0 0 24 24">
              <rect height="7" rx="2" stroke="currentColor" strokeWidth="1.7" width="7" x="3.5" y="3.5" />
              <rect height="7" rx="2" stroke="currentColor" strokeWidth="1.7" width="7" x="13.5" y="3.5" />
              <rect height="7" rx="2" stroke="currentColor" strokeWidth="1.7" width="7" x="3.5" y="13.5" />
              <rect height="7" rx="2" stroke="currentColor" strokeWidth="1.7" width="7" x="13.5" y="13.5" />
            </svg>
          ) : tipo === 'atencao' ? (
            <svg className="size-5" fill="none" viewBox="0 0 24 24">
              <path d="M12 3 2.8 19h18.4L12 3Z" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.7" />
              <path d="M12 9v4m0 3h.01" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
            </svg>
          ) : (
            <svg className="size-5" fill="none" viewBox="0 0 24 24">
              <path d="M4 12h16m-6-6 6 6-6 6" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
              <path d="M4 6v12" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
            </svg>
          )}
        </span>
      </div>
      <p className="metric-card__value">{valor}</p>
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
          <p className="dashboard-kicker">
            <span aria-hidden="true" className="dashboard-kicker__dot" />
            Centro de monitoramento
          </p>
          <h1 className="dashboard-hero__title">Dashboard</h1>
          <p className="dashboard-hero__statement">Cada armadilha, sob controle.</p>
          <p className="dashboard-hero__description">
            Veja as leituras recentes, identifique o que pede atenção e planeje as trocas.
          </p>
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

        <div aria-hidden="true" className="dashboard-hero__art">
          <div className="hero-orbit hero-orbit--outer" />
          <div className="hero-orbit hero-orbit--inner" />
          <div className="hero-trap-illustration">
            <div className="hero-trap-illustration__frame">
              <span />
              <span />
              <span />
              <span />
              <span />
              <span />
              <span />
              <span />
              <span />
            </div>
            <i className="hero-trap-illustration__spark hero-trap-illustration__spark--one" />
            <i className="hero-trap-illustration__spark hero-trap-illustration__spark--two" />
          </div>
          <span className="hero-art-caption">Uma visão, decisões mais claras</span>
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
            <p className="section-kicker">Visão por armadilha</p>
            <h2 className="section-title" id="titulo-armadilhas">
              Armadilhas monitoradas
            </h2>
            <p className="section-description">
              A foto e a última leitura de cada ponto, reunidas em um só lugar.
            </p>
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
