import { useCallback } from 'react'
import Botao from '../components/Botao'
import CartaoArmadilha from '../components/CartaoArmadilha'
import EstadoCarregando from '../components/EstadoCarregando'
import EstadoVazio from '../components/EstadoVazio'
import LinkBotao from '../components/LinkBotao'
import MensagemErro from '../components/MensagemErro'
import PainelAlertas from '../components/PainelAlertas'
import { useCarregamento } from '../hooks/useCarregamento'
import { ApiError } from '../services/erros'
import { listArmadilhas } from '../services/armadilhas'

/** Apresenta os alertas e o estado atual das armadilhas na ordem da API.
 * @returns A tela inicial com alertas, estados vazios e cartões das armadilhas.
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

  return (
    <div className="space-y-8">
      <header className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.14em] text-emerald-900">
            Operação das armadilhas
          </p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">
            Dashboard
          </h1>
          <p className="mt-3 max-w-2xl text-base leading-7 text-slate-700">
            Veja quais refis precisam de atenção e acompanhe a cobertura medida
            em cada armadilha.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <LinkBotao
            to="/analises/nova"
            variante="primario"
          >
            Iniciar análise
          </LinkBotao>
          <LinkBotao
            to="/armadilhas/nova"
            variante="secundario"
          >
            Cadastrar armadilha
          </LinkBotao>
        </div>
      </header>

      <PainelAlertas
        armadilhas={dados}
        carregando={carregando}
        erro={Boolean(erro)}
        instanteReferencia={new Date()}
      />

      <section aria-labelledby="titulo-armadilhas">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-slate-600">
              Estado atual
            </p>
            <h2
              className="mt-1 text-2xl font-semibold tracking-tight text-slate-950"
              id="titulo-armadilhas"
            >
              Armadilhas monitoradas
            </h2>
          </div>
          {dados !== null && !erro && !carregando ? (
            <p className="text-sm font-medium text-slate-700">
              {dados.length === 1
                ? '1 armadilha cadastrada'
                : `${dados.length} armadilhas cadastradas`}
            </p>
          ) : null}
        </div>

        {carregando ? <EstadoCarregando /> : null}
        {erro ? (
          <div className="space-y-4">
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
          <EstadoVazio
            acao={
              <LinkBotao
                to="/armadilhas/nova"
                variante="primario"
              >
                Cadastrar primeira armadilha
              </LinkBotao>
            }
            descricao="Cadastre uma armadilha para acompanhar as análises e a vida útil dos refis."
            titulo="Nenhuma armadilha cadastrada"
          />
        ) : null}
        {!carregando && !erro && dados && dados.length > 0 ? (
          <ul className="grid list-none gap-4 p-0 md:grid-cols-2">
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
