import { useCallback } from 'react'
import { useOutletContext } from 'react-router'
import Botao from '../components/Botao'
import CartaoArmadilha from '../components/CartaoArmadilha'
import LinkBotao from '../components/LinkBotao'
import MensagemErro from '../components/MensagemErro'
import PainelAlertas from '../components/PainelAlertas'
import { useCarregamento } from '../hooks/useCarregamento'
import { CHAVE_ARMADILHAS } from '../lib/cacheLocal'
import { indiceSaturacao } from '../lib/saturacao'
import { ApiError } from '../services/erros'
import { listArmadilhas } from '../services/armadilhas'
import type { ArmadilhaLista } from '../services/tipos'

/** A última lista abre na hora e é atualizada por baixo; o cache é apagado ao sair. */
const CACHE_ARMADILHAS = {
  chave: CHAVE_ARMADILHAS,
  validar: (valor: unknown): valor is ArmadilhaLista[] => Array.isArray(valor),
}

interface ContextoBuscaDashboard {
  termoBusca?: string
}

interface IndicadorProps {
  label: string
  valor: string | number
  detalhe: string
  tipo: 'total' | 'media' | 'atencao' | 'trocar'
  urgente?: boolean
}

function formatarMediaSaturacao(valor: number): string {
  return new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 }).format(valor) + '%'
}

/** Exibe um valor do conjunto filtrado, sem tendência ou comparação presumida. */
function Indicador({ label, valor, detalhe, tipo, urgente = false }: IndicadorProps) {
  return (
    <div
      className={`metric-card metric-card--${tipo}`}
      data-urgente={urgente ? 'true' : undefined}
    >
      <dt className="metric-card__label">{label}</dt>
      <dd className="metric-card__value">{valor}</dd>
      <p className="metric-card__detail">{detalhe}</p>
    </div>
  )
}

function filtrarArmadilhas(armadilhas: ArmadilhaLista[], termo: string): ArmadilhaLista[] {
  const busca = termo.trim().toLocaleLowerCase('pt-BR')
  if (!busca) return armadilhas

  return armadilhas.filter((armadilha) =>
    [armadilha.identificador, armadilha.localizacao, armadilha.modelo]
      .some((campo) => campo?.toLocaleLowerCase('pt-BR').includes(busca)),
  )
}

/** Apresenta o que pede ação hoje e as armadilhas que sustentam essa fila. */
export default function DashboardPage() {
  const loadArmadilhas = useCallback(
    (signal: AbortSignal) => listArmadilhas(signal),
    [],
  )
  const { dados, erro, carregando, recarregar: reload } = useCarregamento(
    loadArmadilhas,
    CACHE_ARMADILHAS,
  )
  // Com dados guardados a tela já aparece; só sem eles vale o esqueleto ou o erro bloqueante.
  const carregandoSemDados = carregando && dados === null
  const atualizando = carregando && dados !== null
  const erroBloqueante = erro !== null && dados === null
  const falhaAoAtualizar = erro !== null && dados !== null
  const contextoBusca = useOutletContext<ContextoBuscaDashboard | null>()
  const termoBusca = contextoBusca?.termoBusca ?? ''
  const armadilhasVisiveis = dados === null ? [] : filtrarArmadilhas(dados, termoBusca)
  const totalAtencao = armadilhasVisiveis.filter((item) => item.status === 'atencao').length
  const totalTroca = armadilhasVisiveis.filter((item) => item.status === 'trocar').length
  const leituras = armadilhasVisiveis.filter(
    (item) => item.refil_ativo !== null && item.percentual_atual !== null,
  )
  const saturacaoMedia = leituras.length
    ? formatarMediaSaturacao(
        leituras.reduce(
          (soma, item) => soma + indiceSaturacao(item.percentual_atual!, item.limiar_trocar),
          0,
        ) / leituras.length,
      )
    : '—'
  const valorIndisponivel = dados === null

  return (
    <div className="dashboard-page page-stack">
      <header className="dashboard-hero">
        <p className="page-kicker">Monitoramento da operação</p>
        <h1 className="dashboard-hero__title">Visão geral</h1>
        <p className="dashboard-hero__description">
          Prioridades de hoje, leituras de saturação e tempo previsto para a próxima troca.
        </p>
      </header>

      <dl aria-label="Resumo das armadilhas" className="metric-grid">
        <Indicador
          detalhe={termoBusca.trim()
            ? `${armadilhasVisiveis.length} ${armadilhasVisiveis.length === 1 ? 'correspondência' : 'correspondências'} na busca`
            : 'em acompanhamento'}
          label="Armadilhas"
          tipo="total"
          valor={valorIndisponivel ? '—' : armadilhasVisiveis.length}
        />
        <Indicador
          detalhe={leituras.length ? `em ${leituras.length} armadilhas com leitura` : 'sem leitura atual'}
          label="Saturação média"
          tipo="media"
          valor={valorIndisponivel ? '—' : saturacaoMedia}
        />
        <Indicador
          detalhe="pedem uma verificação"
          label="Em atenção"
          tipo="atencao"
          valor={valorIndisponivel ? '—' : totalAtencao}
        />
        <Indicador
          detalhe="troca indicada"
          label="Trocar agora"
          tipo="trocar"
          urgente={!valorIndisponivel && totalTroca > 0}
          valor={valorIndisponivel ? '—' : totalTroca}
        />
      </dl>

      <PainelAlertas
        armadilhas={dados === null ? null : armadilhasVisiveis}
        carregando={carregandoSemDados}
        erro={erroBloqueante}
        instanteReferencia={new Date()}
      />

      <section aria-labelledby="titulo-armadilhas" className="dashboard-section">
        <div className="section-heading">
          <div>
            <h2 className="section-title" id="titulo-armadilhas">
              Armadilhas monitoradas
            </h2>
            <p className="section-description">
              {termoBusca.trim()
                ? `Resultados para “${termoBusca.trim()}”.`
                : 'Cada cartão mostra a leitura mais recente e o prazo até a saturação.'}
            </p>
          </div>
          {atualizando ? (
            <span className="section-count" role="status">Atualizando…</span>
          ) : dados !== null ? (
            <span className="section-count">
              {armadilhasVisiveis.length === 1
                ? '1 armadilha'
                : `${armadilhasVisiveis.length} armadilhas`}
            </span>
          ) : null}
        </div>

        {carregandoSemDados ? (
          <ul aria-label="Carregando armadilhas" aria-busy="true" className="trap-grid trap-grid--loading">
            {Array.from({ length: 4 }, (_, indice) => (
              <li aria-hidden="true" className="trap-card-skeleton" key={indice}>
                <span className="skeleton-block skeleton-block--thumb" />
                <span className="skeleton-block skeleton-block--title" />
                <span className="skeleton-block skeleton-block--reading" />
              </li>
            ))}
          </ul>
        ) : null}

        {falhaAoAtualizar ? (
          <p className="empty-state-panel" role="status">
            Não foi possível atualizar. Mostrando os dados da última visita.
          </p>
        ) : null}

        {erroBloqueante ? (
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

        {dados?.length === 0 ? (
          <section aria-labelledby="titulo-vazio" className="empty-state-panel">
            <h3 className="section-title" id="titulo-vazio">Nenhuma armadilha cadastrada</h3>
            <p className="section-description">
              Cadastre a primeira armadilha para começar a acompanhar as leituras e os refis.
            </p>
            <LinkBotao to="/armadilhas/nova" variante="primario">
              Cadastrar primeira armadilha
            </LinkBotao>
          </section>
        ) : null}

        {dados && dados.length > 0 && armadilhasVisiveis.length === 0 ? (
          <p className="empty-state-panel" role="status">
            Nenhuma armadilha encontrada para “{termoBusca.trim()}”.
          </p>
        ) : null}

        {armadilhasVisiveis.length > 0 ? (
          <ul className="trap-grid">
            {armadilhasVisiveis.map((armadilha) => (
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
