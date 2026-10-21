import { useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router'
import { useAuth } from '../auth/useAuth'
import Botao from './Botao'
import LinkBotao from './LinkBotao'
import MarcaTrapSight from './MarcaTrapSight'
import MensagemErro from './MensagemErro'

const classesDeLink = ({ isActive }: { isActive: boolean }) =>
  [
    'min-h-11 rounded-lg px-3 py-2.5 text-sm font-semibold transition-colors',
    'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-800',
    isActive
      ? 'bg-emerald-50 text-emerald-950 ring-1 ring-inset ring-emerald-200'
      : 'text-slate-700 hover:bg-slate-100 hover:text-slate-950',
  ].join(' ')

/** Apresenta a identidade, a navegação e a conta do usuário, presentes em todas as rotas. */
export default function Layout() {
  const { ativa, usuario, logout } = useAuth()
  const [erroSaida, setErroSaida] = useState<string | null>(null)

  async function sair() {
    setErroSaida(null)
    try {
      await logout()
    } catch {
      setErroSaida('Não foi possível encerrar a sessão. Tente novamente.')
    }
  }

  return (
    <div className="min-h-screen bg-stone-50 text-slate-950">
      <a
        className="absolute left-4 top-4 z-10 -translate-y-24 rounded-lg bg-white px-4 py-3 font-semibold text-emerald-950 shadow-lg transition-transform focus:translate-y-0 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-800"
        href="#conteudo-principal"
      >
        Pular para o conteúdo
      </a>

      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-4 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <Link
            aria-label="TrapSight — início"
            className="inline-flex min-h-11 w-fit items-center gap-3 rounded-lg text-xl font-bold tracking-tight text-emerald-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-800"
            to="/"
          >
            <MarcaTrapSight />
          </Link>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-6">
            <nav aria-label="Navegação principal" className="flex flex-wrap gap-2">
              <NavLink className={classesDeLink} end to="/">
                Dashboard
              </NavLink>
              <NavLink className={classesDeLink} end to="/analises/nova">
                Nova análise
              </NavLink>
              <NavLink className={classesDeLink} end to="/armadilhas/nova">
                Nova armadilha
              </NavLink>
            </nav>

            {ativa && usuario ? (
              <div
                aria-label="Conta"
                className="flex flex-wrap items-center gap-2 border-slate-200 sm:border-l sm:pl-6"
                role="group"
              >
                <span className="text-sm font-medium text-slate-700" title={usuario.nome}>
                  {usuario.email}
                </span>
                <LinkBotao tamanho="compacto" to="/conta/senha" variante="discreto">
                  Alterar senha
                </LinkBotao>
                <Botao onClick={() => void sair()} tamanho="compacto" variante="secundario">
                  Sair
                </Botao>
              </div>
            ) : null}
          </div>
        </div>
      </header>

      <main
        className="mx-auto min-h-[calc(100vh-8rem)] w-full max-w-6xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8"
        id="conteudo-principal"
        tabIndex={-1}
      >
        {erroSaida ? (
          <div className="mb-6">
            <MensagemErro erro={erroSaida} />
          </div>
        ) : null}
        <Outlet />
      </main>
    </div>
  )
}
