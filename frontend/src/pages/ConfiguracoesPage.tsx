import { Link, useOutletContext } from 'react-router'
import type { Tema } from '../hooks/useTema'

interface ContextoConfiguracoes {
  alternarTema: () => void
  tema: Tema
}

/** Reúne as preferências visuais e o acesso à segurança da própria conta. */
export default function ConfiguracoesPage() {
  const { alternarTema, tema } = useOutletContext<ContextoConfiguracoes>()

  function selecionarTema(novoTema: Tema) {
    if (novoTema !== tema) alternarTema()
  }

  return (
    <div className="page-stack settings-page">
      <header className="page-header">
        <p className="page-kicker">Preferências da conta</p>
        <h1 className="page-title">Configurações</h1>
        <p className="page-description">
          Ajuste a aparência do TrapSight e mantenha sua conta protegida.
        </p>
      </header>

      <section aria-labelledby="settings-appearance-title" className="surface-panel settings-card">
        <div className="settings-card__heading">
          <span aria-hidden="true" className="settings-card__icon">
            <svg fill="none" viewBox="0 0 24 24">
              <path d="M20.2 15.2A8.2 8.2 0 0 1 8.8 3.8a8.2 8.2 0 1 0 11.4 11.4Z" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.7" />
              <path d="M16.5 3v3m-1.5-1.5h3" stroke="currentColor" strokeLinecap="round" strokeWidth="1.5" />
            </svg>
          </span>
          <div>
            <h2 className="settings-card__title" id="settings-appearance-title">Aparência</h2>
            <p className="settings-card__description">
              Escolha o tema usado nas telas e nos painéis de monitoramento.
            </p>
          </div>
        </div>

        <div aria-label="Tema do aplicativo" className="settings-theme-options" role="group">
          <button
            aria-pressed={tema === 'claro'}
            className={`settings-theme-choice${tema === 'claro' ? ' settings-theme-choice--selected' : ''}`}
            onClick={() => selecionarTema('claro')}
            type="button"
          >
            <svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
              <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="1.7" />
              <path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42" stroke="currentColor" strokeLinecap="round" strokeWidth="1.7" />
            </svg>
            <span className="settings-theme-choice__title">Claro</span>
            <span className="settings-theme-choice__description">Fundo claro e alto contraste.</span>
          </button>
          <button
            aria-pressed={tema === 'escuro'}
            className={`settings-theme-choice${tema === 'escuro' ? ' settings-theme-choice--selected' : ''}`}
            onClick={() => selecionarTema('escuro')}
            type="button"
          >
            <svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
              <path d="M20.2 15.2A8.2 8.2 0 0 1 8.8 3.8a8.2 8.2 0 1 0 11.4 11.4Z" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.7" />
            </svg>
            <span className="settings-theme-choice__title">Escuro</span>
            <span className="settings-theme-choice__description">Superfícies profundas para baixa luminosidade.</span>
          </button>
        </div>
        <p className="settings-card__note" role="status">
          A preferência é salva automaticamente neste navegador.
        </p>
      </section>

      <section aria-labelledby="settings-security-title" className="surface-panel settings-card">
        <div className="settings-card__heading">
          <span aria-hidden="true" className="settings-card__icon">
            <svg fill="none" viewBox="0 0 24 24">
              <path d="M7 10V7a5 5 0 0 1 10 0v3m-12 0h14v10H5V10Zm7 4v2" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.7" />
            </svg>
          </span>
          <div>
            <h2 className="settings-card__title" id="settings-security-title">Segurança da conta</h2>
            <p className="settings-card__description">
              Atualize sua senha para manter o acesso protegido.
            </p>
          </div>
        </div>

        <div className="settings-security-row">
          <div>
            <h3 className="settings-security-row__title">Senha</h3>
            <p className="settings-card__description">
              Você precisará informar a senha atual. As outras sessões serão encerradas.
            </p>
          </div>
          <Link className="settings-action" to="/conta/senha">
            Alterar senha
            <svg aria-hidden="true" fill="none" viewBox="0 0 20 20">
              <path d="M4 10h12m-5-5 5 5-5 5" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.6" />
            </svg>
          </Link>
        </div>
      </section>
    </div>
  )
}
