import { formatData } from '../lib/formatacao'
import type { ArmadilhaDetalhe } from '../services/tipos'
import LinkBotao from './LinkBotao'

interface ResumoArmadilhaProps {
  armadilha: ArmadilhaDetalhe
}

/** Apresenta os dados de cadastro e os atalhos principais da armadilha.
 * @param props Armadilha carregada pela API.
 * @returns Cabeçalho com identificação, localização, instalação e navegação.
 */
export default function ResumoArmadilha({ armadilha }: ResumoArmadilhaProps) {
  return (
    <header className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <p className="text-sm font-semibold uppercase tracking-[0.14em] text-emerald-900">
          Detalhe da armadilha
        </p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">
          {armadilha.identificador}
        </h1>
        <dl className="mt-4 grid gap-x-6 gap-y-2 text-sm text-slate-700 sm:grid-cols-2">
          <div>
            <dt className="font-semibold text-slate-900">Modelo</dt>
            <dd>{armadilha.modelo ?? 'Não informado'}</dd>
          </div>
          <div>
            <dt className="font-semibold text-slate-900">Localização</dt>
            <dd>{armadilha.localizacao ?? 'Não informada'}</dd>
          </div>
          <div>
            <dt className="font-semibold text-slate-900">Data de instalação</dt>
            <dd>
              {armadilha.data_instalacao
                ? formatData(armadilha.data_instalacao)
                : 'Não informada'}
            </dd>
          </div>
        </dl>
      </div>
      <nav aria-label="Ações da armadilha" className="flex flex-wrap gap-2">
        <LinkBotao
          to={`/armadilhas/${armadilha.id}/editar`}
          variante="secundario"
        >
          Editar armadilha
        </LinkBotao>
        <LinkBotao to="/analises/nova" variante="primario">
          Nova análise
        </LinkBotao>
      </nav>
    </header>
  )
}
