import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router'
import { useAuth } from '../auth/useAuth'
import { useModoInstalado } from '../hooks/useInstalacao'
import { useTema } from '../hooks/useTema'
import MarcaTrapSight from './MarcaTrapSight'
import MensagemErro from './MensagemErro'

const CHAVE_SIDEBAR = 'trapsight:sidebar-recolhida'

interface IconeNavegacaoProps {
  tipo: 'painel' | 'analise' | 'armadilha' | 'contas' | 'configuracoes'
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
      ) : tipo === 'contas' ? (
        <>
          <circle cx="9" cy="8" r="3" stroke="currentColor" strokeWidth="1.7" />
          <path d="M3 20v-2a6 6 0 0 1 12 0v2m2-15a3 3 0 0 1 0 6m2 3a5 5 0 0 1 2 4v2" stroke="currentColor" strokeLinecap="round" strokeWidth="1.7" />
        </>
      ) : tipo === 'armadilha' ? (
        <>
          <rect height="16" rx="3" stroke="currentColor" strokeWidth="1.7" width="16" x="3" y="3" />
          <path d="M7 7h8M7 10h8M7 13h4m5 2v5m-2.5-2.5h5" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.7" />
        </>
      ) : (
        <>
          <path d="M12 8.8a3.2 3.2 0 1 0 0 6.4 3.2 3.2 0 0 0 0-6.4Z" stroke="currentColor" strokeWidth="1.7" />
          <path d="m19.4 15 .1.1a1.7 1.7 0 0 1-2.4 2.4l-.1-.1a1.7 1.7 0 0 0-2.9 1.2v.2a1.7 1.7 0 0 1-3.4 0v-.2a1.7 1.7 0 0 0-2.9-1.2l-.1.1a1.7 1.7 0 1 1-2.4-2.4l.1-.1a1.7 1.7 0 0 0-1.2-2.9H4a1.7 1.7 0 0 1 0-3.4h.2a1.7 1.7 0 0 0 1.2-2.9l-.1-.1a1.7 1.7 0 1 1 2.4-2.4l.1.1a1.7 1.7 0 0 0 2.9-1.2V2a1.7 1.7 0 0 1 3.4 0v.2a1.7 1.7 0 0 0 2.9 1.2l.1-.1a1.7 1.7 0 1 1 2.4 2.4l-.1.1a1.7 1.7 0 0 0 1.2 2.9h.2a1.7 1.7 0 0 1 0 3.4h-.2a1.7 1.7 0 0 0-1.2 2.9Z" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" transform="translate(1 1) scale(.91)" />
        </>
      )}
    </svg>
  )
}

interface MenuContaProps {
  nome: string
  aoSair: () => void
  variante: 'sidebar' | 'bottom'
}

/** Agrupa as ações da conta atrás do avatar para liberar espaço na navegação.
 * No celular o avatar fica na barra inferior; na lateral, junto ao nome.
 */
function MenuConta({ nome, aoSair, variante }: MenuContaProps) {
  const [aberto, setAberto] = useState(false)
  const ancoraRef = useRef<HTMLDivElement>(null)
  const idMenu = `menu-conta-${variante}`

  useEffect(() => {
    if (!aberto) return

    function fecharAoClicarFora(evento: PointerEvent) {
      if (!ancoraRef.current?.contains(evento.target as Node)) setAberto(false)
    }

    function fecharComEscape(evento: KeyboardEvent) {
      if (evento.key !== 'Escape') return
      setAberto(false)
      ancoraRef.current?.querySelector<HTMLButtonElement>('.account-menu-trigger')?.focus()
    }

    document.addEventListener('pointerdown', fecharAoClicarFora)
    window.addEventListener('keydown', fecharComEscape)
    return () => {
      document.removeEventListener('pointerdown', fecharAoClicarFora)
      window.removeEventListener('keydown', fecharComEscape)
    }
  }, [aberto])

  return (
    <div className={`account-menu-anchor account-menu-anchor--${variante}`} ref={ancoraRef}>
      <button
        aria-controls={idMenu}
        aria-expanded={aberto}
        aria-label={`Abrir opções da conta de ${nome}`}
        className={`account-menu-trigger${variante === 'bottom' ? ' account-menu-trigger--bottom mobile-nav-link' : ''}`}
        onClick={() => setAberto((atual) => !atual)}
        title={nome}
        type="button"
      >
        <span aria-hidden="true" className="account-avatar">
          {nome.trim().slice(0, 1).toLocaleUpperCase('pt-BR')}
        </span>
        {variante === 'sidebar' ? (
          <span className="account-menu-trigger__name">{nome}</span>
        ) : (
          <span aria-hidden="true">Perfil</span>
        )}
      </button>
      {aberto ? (
        <div aria-label="Opções da conta" className="account-menu" id={idMenu}>
          <div className="account-menu__identity">
            <span className="account-menu__eyebrow">Conta ativa</span>
            <span className="account-menu__name">{nome}</span>
          </div>
          <Link className="account-menu__item" onClick={() => setAberto(false)} to="/configuracoes">
            <IconeNavegacao tipo="configuracoes" />
            <span>Configurações</span>
          </Link>
          <button
            className="account-menu__item account-menu__item--signout"
            onClick={() => {
              setAberto(false)
              aoSair()
            }}
            type="button"
          >
            <svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
              <path d="M14 8V5H5v14h9v-3m-4-4h9m0 0-3-3m3 3-3 3" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.7" />
            </svg>
            <span>Sair</span>
          </button>
        </div>
      ) : null}
    </div>
  )
}

/** Retorna a preferência persistida da sidebar sem bloquear a interface.
 * @returns `true` quando a navegação deve iniciar recolhida.
 */
function lerSidebarRecolhida(): boolean {
  try {
    return window.localStorage.getItem(CHAVE_SIDEBAR) !== 'nao'
  } catch {
    return true
  }
}

/** Apresenta marca, navegação responsiva, conta e o conteúdo da rota atual. */
export default function Layout() {
  const { ativa, usuario, logout } = useAuth()
  const { pathname } = useLocation()
  const modoInstalado = useModoInstalado()
  const { tema, alternarTema } = useTema()
  const [erroSaida, setErroSaida] = useState<string | null>(null)
  const [sidebarRecolhida, setSidebarRecolhida] = useState(lerSidebarRecolhida)
  const [termoBusca, setTermoBusca] = useState('')
  const campoBuscaRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const raiz = document.documentElement
    if (modoInstalado) {
      raiz.setAttribute('data-modo-instalado', 'true')
    } else {
      raiz.removeAttribute('data-modo-instalado')
    }

    return () => raiz.removeAttribute('data-modo-instalado')
  }, [modoInstalado])

  useEffect(() => {
    function tratarAtalho(evento: KeyboardEvent) {
      if (
        campoBuscaRef.current &&
        (evento.ctrlKey || evento.metaKey) &&
        evento.key.toLocaleLowerCase() === 'k'
      ) {
        evento.preventDefault()
        campoBuscaRef.current?.focus()
      }

      if (evento.key === 'Escape' && document.activeElement === campoBuscaRef.current) {
        setTermoBusca('')
        campoBuscaRef.current?.blur()
      }
    }

    window.addEventListener('keydown', tratarAtalho)
    return () => window.removeEventListener('keydown', tratarAtalho)
  }, [])

  useEffect(() => {
    try {
      window.localStorage.setItem(CHAVE_SIDEBAR, sidebarRecolhida ? 'sim' : 'nao')
    } catch {
      // A navegação segue funcionando sem persistir a preferência.
    }
  }, [sidebarRecolhida])

  const tituloDaRota = pathname === '/'
    ? 'Visão geral'
    : pathname === '/contas'
      ? 'Contas'
      : pathname.startsWith('/analises')
      ? 'Nova análise'
      : pathname === '/conta/senha'
        ? 'Segurança da conta'
        : pathname === '/configuracoes'
          ? 'Configurações'
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
            <MarcaTrapSight variante="reversa" />
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
          <p className="sidebar-group-label">Monitoramento</p>
          <NavLink aria-label="Dashboard" className={classeLink} end title="Dashboard" to="/">
            <IconeNavegacao tipo="painel" />
            <span className="sidebar-link-label">Dashboard</span>
          </NavLink>

          <p className="sidebar-group-label sidebar-group-label--spaced">Operação</p>
          <NavLink aria-label="Nova análise" className={classeLink} end title="Nova análise" to="/analises/nova">
            <IconeNavegacao tipo="analise" />
            <span className="sidebar-link-label">Nova análise</span>
          </NavLink>
          <NavLink aria-label="Nova armadilha" className={classeLink} end title="Nova armadilha" to="/armadilhas/nova">
            <IconeNavegacao tipo="armadilha" />
            <span className="sidebar-link-label">Nova armadilha</span>
          </NavLink>
          {usuario?.papel === 'gerente' ? (
            <NavLink aria-label="Contas" className={classeLink} title="Contas" to="/contas">
              <IconeNavegacao tipo="contas" />
              <span className="sidebar-link-label">Contas</span>
            </NavLink>
          ) : null}
        </nav>

        <div className="sidebar-bottom">
          {ativa && usuario ? (
            <div className="sidebar-account">
              <MenuConta aoSair={() => void sair()} nome={usuario.nome} variante="sidebar" />
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
          <Link aria-label="Ir para o início" className="topbar-logo" to="/">
            <MarcaTrapSight />
          </Link>
          <div className="topbar-context">
            <span aria-hidden="true" className="topbar-context-mark" />
            <span className="topbar-context-name">TrapSight</span>
            <span aria-hidden="true" className="topbar-separator">/</span>
            <span className="topbar-current-page">{tituloDaRota}</span>
          </div>
          {pathname === '/' ? (
            <label className="topbar-search">
              <svg aria-hidden="true" fill="none" viewBox="0 0 20 20">
                <circle cx="8.75" cy="8.75" r="5.75" stroke="currentColor" strokeWidth="1.5" />
                <path d="m13 13 4 4" stroke="currentColor" strokeLinecap="round" strokeWidth="1.5" />
              </svg>
              <span className="sr-only">Buscar armadilha</span>
              <input
                aria-keyshortcuts="Control+K Meta+K"
                autoComplete="off"
                name="busca_armadilha"
                onChange={(evento) => setTermoBusca(evento.currentTarget.value)}
                placeholder="Buscar armadilha"
                ref={campoBuscaRef}
                type="search"
                value={termoBusca}
              />
              <kbd aria-hidden="true">Ctrl K</kbd>
            </label>
          ) : null}
          <div className="topbar-actions">
            {pathname === '/' ? (
              <Link aria-label="Nova análise" className="topbar-primary" to="/analises/nova">
                <svg aria-hidden="true" fill="none" viewBox="0 0 20 20">
                  <path d="M10 3v14M3 10h14" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
                </svg>
                <span>Nova análise</span>
              </Link>
            ) : null}
          </div>
        </header>

        <main className="app-main" id="conteudo-principal" tabIndex={-1}>
          {erroSaida ? <MensagemErro erro={erroSaida} /> : null}
          <Outlet context={{ alternarTema, tema, termoBusca, setTermoBusca }} />
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
          {usuario?.papel === 'gerente' ? (
            <NavLink aria-label="Contas" className={classeLinkMovel} to="/contas">
              <IconeNavegacao tipo="contas" />
              <span>Contas</span>
            </NavLink>
          ) : null}
          {usuario ? (
            <MenuConta aoSair={() => void sair()} nome={usuario.nome} variante="bottom" />
          ) : null}
        </nav>
      ) : null}
    </div>
  )
}
