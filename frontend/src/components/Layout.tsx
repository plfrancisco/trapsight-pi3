import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router'
import { useAuth } from '../auth/useAuth'
import { useTema } from '../hooks/useTema'
import ControleTema from './ControleTema'
import MarcaTrapSight from './MarcaTrapSight'
import MensagemErro from './MensagemErro'

const CHAVE_SIDEBAR = 'trapsight:sidebar-recolhida'

interface IconeNavegacaoProps {
  tipo: 'painel' | 'analise' | 'armadilha'
}

/** Desenha os ícones vetoriais usados na navegação principal.
 * @param props Tipo de seção representada pelo ícone.
 * @returns Um ícone decorativo coerente com a ação correspondente.
 */
function IconeNavegacao({ tipo }: IconeNavegacaoProps) {
  return (
    <svg aria-hidden="true" className="size-5 shrink-0" fill="none" viewBox="0 0 24 24">
      {tipo === 'painel' ? (
        <>
          <rect height="7" rx="2" stroke="currentColor" strokeWidth="1.7" width="7" x="3.5" y="3.5" />
          <rect height="7" rx="2" stroke="currentColor" strokeWidth="1.7" width="7" x="13.5" y="3.5" />
          <rect height="7" rx="2" stroke="currentColor" strokeWidth="1.7" width="7" x="3.5" y="13.5" />
          <rect height="7" rx="2" stroke="currentColor" strokeWidth="1.7" width="7" x="13.5" y="13.5" />
        </>
      ) : tipo === 'analise' ? (
        <>
          <path d="M4 8.5h16v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-10Z" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.7" />
          <path d="m8 8.5 1.3-3h5.4l1.3 3M9 13h6m-3-3v6" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.7" />
        </>
      ) : (
        <>
          <rect height="16" rx="3" stroke="currentColor" strokeWidth="1.7" width="16" x="3" y="3" />
          <path d="M7 7h8M7 10h8M7 13h4m5 2v5m-2.5-2.5h5" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.7" />
        </>
      )}
    </svg>
  )
}

/** Retorna a preferência persistida da sidebar sem bloquear a interface.
 * @returns `true` quando a navegação deve iniciar recolhida.
 */
function lerSidebarRecolhida(): boolean {
  try {
    return window.localStorage.getItem(CHAVE_SIDEBAR) === 'sim'
  } catch {
    return false
  }
}

/** Apresenta marca, navegação responsiva, conta e o conteúdo da rota atual. */
export default function Layout() {
  const { ativa, usuario, logout } = useAuth()
  const { pathname } = useLocation()
  const { tema, alternarTema } = useTema()
  const [erroSaida, setErroSaida] = useState<string | null>(null)
  const [sidebarRecolhida, setSidebarRecolhida] = useState(lerSidebarRecolhida)

  useEffect(() => {
    try {
      window.localStorage.setItem(CHAVE_SIDEBAR, sidebarRecolhida ? 'sim' : 'nao')
    } catch {
      // A navegação segue funcionando sem persistir a preferência.
    }
  }, [sidebarRecolhida])

  const tituloDaRota = pathname === '/'
    ? 'Visão geral'
    : pathname.startsWith('/analises')
      ? 'Nova análise'
      : pathname === '/conta/senha'
        ? 'Segurança da conta'
        : pathname.endsWith('/editar')
          ? 'Editar armadilha'
          : pathname.startsWith('/armadilhas/') && pathname !== '/armadilhas/nova'
            ? 'Detalhe da armadilha'
            : 'Nova armadilha'

  async function sair() {
    setErroSaida(null)
    try {
      await logout()
    } catch {
      setErroSaida('Não foi possível encerrar a sessão. Tente novamente.')
    }
  }

  function alternarSidebar() {
    setSidebarRecolhida((recolhida) => !recolhida)
  }

  const classeLink = ({ isActive }: { isActive: boolean }) =>
    `sidebar-link${isActive ? ' sidebar-link--active' : ''}`

  const classeLinkMovel = ({ isActive }: { isActive: boolean }) =>
    `mobile-nav-link${isActive ? ' mobile-nav-link--active' : ''}`

  return (
    <div className={`app-shell${sidebarRecolhida ? ' app-shell--compact' : ''}`}>
      <a className="skip-link" href="#conteudo-principal">
        Pular para o conteúdo
      </a>

      <aside aria-label="Menu principal" className="app-sidebar">
        <div className="sidebar-brand-row">
          <Link aria-label="TrapSight — início" className="sidebar-brand" to="/">
            <MarcaTrapSight />
          </Link>
          <button
            aria-controls="navegacao-principal"
            aria-expanded={!sidebarRecolhida}
            aria-label={sidebarRecolhida ? 'Expandir menu lateral' : 'Recolher menu lateral'}
            className="sidebar-collapse"
            onClick={alternarSidebar}
            title={sidebarRecolhida ? 'Expandir menu lateral' : 'Recolher menu lateral'}
            type="button"
          >
            <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24">
              <path d={sidebarRecolhida ? 'm9 5 7 7-7 7' : 'm15 5-7 7 7 7'} stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
            </svg>
          </button>
        </div>

        <nav aria-label="Navegação principal" className="sidebar-navigation" id="navegacao-principal">
          <p className="sidebar-group-label">Workspace</p>
          <NavLink aria-label="Dashboard" className={classeLink} end title={sidebarRecolhida ? 'Dashboard' : undefined} to="/">
            <IconeNavegacao tipo="painel" />
            <span className="sidebar-link-label">Dashboard</span>
          </NavLink>

          <p className="sidebar-group-label sidebar-group-label--spaced">Operação</p>
          <NavLink aria-label="Nova análise" className={classeLink} end title={sidebarRecolhida ? 'Nova análise' : undefined} to="/analises/nova">
            <IconeNavegacao tipo="analise" />
            <span className="sidebar-link-label">Nova análise</span>
          </NavLink>
          <NavLink aria-label="Nova armadilha" className={classeLink} end title={sidebarRecolhida ? 'Nova armadilha' : undefined} to="/armadilhas/nova">
            <IconeNavegacao tipo="armadilha" />
            <span className="sidebar-link-label">Nova armadilha</span>
          </NavLink>
        </nav>

        <div className="sidebar-bottom">
          {ativa && usuario ? (
            <div className="sidebar-account">
              <span aria-hidden="true" className="account-avatar">
                {usuario.nome.trim().slice(0, 1).toLocaleUpperCase('pt-BR')}
              </span>
              <span className="sidebar-account-copy">
                <span className="sidebar-account-name">{usuario.nome}</span>
                <span className="sidebar-account-email" title={usuario.email}>{usuario.email}</span>
              </span>
            </div>
          ) : null}
        </div>
      </aside>

      <div className="app-workspace">
        <header className="mobile-header">
          <Link aria-label="TrapSight — início" className="sidebar-brand" to="/">
            <MarcaTrapSight />
          </Link>
        </header>

        <header aria-label="Barra superior" className="workspace-topbar">
          <div className="topbar-context">
            <span aria-hidden="true" className="topbar-context-mark" />
            <span>TrapSight</span>
            <span aria-hidden="true" className="topbar-separator">/</span>
            <span className="topbar-current-page">{tituloDaRota}</span>
          </div>
          <div className="topbar-actions">
            <ControleTema compacto onAlternar={alternarTema} tema={tema} />
            {ativa && usuario ? (
              <>
                <span className="topbar-user" title={usuario.email}>{usuario.nome}</span>
                <Link aria-label="Alterar senha" className="account-action" title="Alterar senha" to="/conta/senha">
                  <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24">
                    <path d="M7 10V7a5 5 0 0 1 10 0v3m-12 0h14v10H5V10Zm7 4v2" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.7" />
                  </svg>
                </Link>
                <button aria-label="Sair" className="account-action" onClick={() => void sair()} title="Sair" type="button">
                  <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24">
                    <path d="M14 8V5H5v14h9v-3m-4-4h9m0 0-3-3m3 3-3 3" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.7" />
                  </svg>
                </button>
              </>
            ) : null}
          </div>
        </header>

        <main className="app-main" id="conteudo-principal" tabIndex={-1}>
          {erroSaida ? <MensagemErro erro={erroSaida} /> : null}
          <Outlet />
        </main>
      </div>

      {ativa ? (
        <nav aria-label="Navegação móvel" className="mobile-bottom-nav">
          <NavLink aria-label="Dashboard" className={classeLinkMovel} end to="/">
            <IconeNavegacao tipo="painel" />
            <span>Início</span>
          </NavLink>
          <NavLink aria-label="Nova análise" className={classeLinkMovel} end to="/analises/nova">
            <IconeNavegacao tipo="analise" />
            <span>Analisar</span>
          </NavLink>
          <NavLink aria-label="Nova armadilha" className={classeLinkMovel} end to="/armadilhas/nova">
            <IconeNavegacao tipo="armadilha" />
            <span>Armadilha</span>
          </NavLink>
        </nav>
      ) : null}
    </div>
  )
}
