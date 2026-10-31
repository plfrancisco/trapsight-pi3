import { formatData } from '../lib/formatacao'
import type { ArmadilhaDetalhe } from '../services/tipos'
import AcaoExcluirArmadilha from './AcaoExcluirArmadilha'
import FotoArmadilha from './FotoArmadilha'
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
    <header className="detail-hero">
      <figure className="detail-hero__photo">
        <FotoArmadilha
          fotoTipo={armadilha.foto_tipo}
          fotoUrl={armadilha.foto_url}
          identificador={armadilha.identificador}
          key={armadilha.foto_url ?? 'padrao'}
          modelo={armadilha.modelo}
        />
      </figure>
      <div className="detail-hero__info">
        <p className="page-kicker">
          Detalhe da armadilha
        </p>
        <h1 className="page-title">
          {armadilha.identificador}
        </h1>
        <dl className="detail-hero__meta">
          <div>
            <dt>Modelo</dt>
            <dd>{armadilha.modelo ?? 'Não informado'}</dd>
          </div>
          <div>
            <dt>Localização</dt>
            <dd>{armadilha.localizacao ?? 'Não informada'}</dd>
          </div>
          <div>
            <dt>Data de instalação</dt>
            <dd>
              {armadilha.data_instalacao
                ? formatData(armadilha.data_instalacao)
                : 'Não informada'}
            </dd>
          </div>
        </dl>
        {armadilha.removida_em ? (
          <p className="detail-hero__removed" role="status">
            Removida do painel. O histórico permanece disponível para consulta.
          </p>
        ) : null}
      </div>
      <nav aria-label="Ações da armadilha" className="detail-hero__actions">
        {armadilha.removida_em ? (
          <LinkBotao to="/" variante="secundario">Voltar ao painel</LinkBotao>
        ) : (
          <>
            <LinkBotao
              to={`/armadilhas/${armadilha.id}/editar`}
              variante="secundario"
            >
              Editar armadilha
            </LinkBotao>
            <LinkBotao to="/analises/nova" variante="primario">
              Nova análise
            </LinkBotao>
            <AcaoExcluirArmadilha
              armadilhaId={armadilha.id}
              identificador={armadilha.identificador}
            />
          </>
        )}
      </nav>
    </header>
  )
}
