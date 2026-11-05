/** Mostra a silhueta de uma tela enquanto a sessão é verificada, no lugar de uma página em branco. */
export default function EsqueletoSessao() {
  return (
    <div aria-busy="true" aria-live="polite" className="esqueleto-sessao" role="status">
      <span className="sr-only">Carregando…</span>
      <div aria-hidden="true" className="esqueleto-sessao__topo">
        <span className="skeleton-block esqueleto-sessao__logo" />
        <span className="skeleton-block esqueleto-sessao__busca" />
      </div>
      <div aria-hidden="true" className="esqueleto-sessao__titulo">
        <span className="skeleton-block esqueleto-sessao__linha esqueleto-sessao__linha--curta" />
        <span className="skeleton-block esqueleto-sessao__linha esqueleto-sessao__linha--longa" />
      </div>
      <div aria-hidden="true" className="esqueleto-sessao__cartoes">
        <span className="skeleton-block esqueleto-sessao__cartao" />
        <span className="skeleton-block esqueleto-sessao__cartao" />
        <span className="skeleton-block esqueleto-sessao__cartao" />
      </div>
    </div>
  )
}
