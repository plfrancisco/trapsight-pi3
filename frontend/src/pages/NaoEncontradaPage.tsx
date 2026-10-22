import LinkBotao from '../components/LinkBotao'

/** Informa que o endereço solicitado não corresponde a uma tela disponível. */
export default function NaoEncontradaPage() {
  return (
    <section aria-labelledby="titulo-nao-encontrada" className="empty-state-panel">
      <span aria-hidden="true" className="empty-state-panel__mark">
        <svg className="size-7" fill="none" viewBox="0 0 28 28">
          <circle cx="12.5" cy="12.5" r="7.5" stroke="currentColor" strokeWidth="1.7" />
          <path d="m18 18 5 5M12.5 9.5v3m0 3h.01" stroke="currentColor" strokeLinecap="round" strokeWidth="1.7" />
        </svg>
      </span>
      <h1 className="section-title" id="titulo-nao-encontrada">
        Página não encontrada
      </h1>
      <p className="section-description">
        O endereço solicitado não corresponde a uma página disponível.
      </p>
      <LinkBotao to="/" variante="primario">
        Voltar ao dashboard
      </LinkBotao>
    </section>
  )
}
