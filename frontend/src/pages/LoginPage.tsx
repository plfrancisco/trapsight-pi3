import { useRef, useState, type FormEvent } from 'react'
import { Navigate, useLocation } from 'react-router'
import { useAuth } from '../auth/useAuth'
import Botao from '../components/Botao'
import CampoFormulario from '../components/CampoFormulario'
import EstadoCarregando from '../components/EstadoCarregando'
import MarcaTrapSight from '../components/MarcaTrapSight'
import MensagemErro from '../components/MensagemErro'
import { mensagemDeLogin } from '../lib/autenticacao'
import { destinoDoEstado } from '../lib/destino'

/** Autentica o usuário e o leva ao destino que ele tentava acessar.
 * @returns A tela de login, ou o redirecionamento quando já há sessão.
 */
export default function LoginPage() {
  const { ativa, estado, motivoSaida, login } = useAuth()
  const localizacao = useLocation()
  const referenciaSenha = useRef<HTMLInputElement>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  // Com sessão (ou com a autenticação desligada) não há o que fazer aqui.
  if (!ativa || estado === 'autenticado') {
    return <Navigate replace to={destinoDoEstado(localizacao.state)} />
  }

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const formulario = new FormData(evento.currentTarget)
    const email = String(formulario.get('email') ?? '').trim()
    const senha = String(formulario.get('senha') ?? '')

    if (!email || !senha) {
      setErro('Informe o e-mail e a senha.')
      return
    }

    setEnviando(true)
    setErro(null)
    try {
      await login(email, senha)
    } catch (falha: unknown) {
      setErro(mensagemDeLogin(falha))
      // Uma senha recusada não fica na tela.
      if (referenciaSenha.current) referenciaSenha.current.value = ''
      referenciaSenha.current?.focus()
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="min-h-screen bg-stone-50 px-4 py-12 text-slate-950">
      <main className="mx-auto w-full max-w-md space-y-8" id="conteudo-principal">
        <div className="flex items-center gap-3 text-xl font-bold tracking-tight text-emerald-950">
          <MarcaTrapSight />
        </div>

        <header>
          <h1 className="text-3xl font-bold tracking-tight text-slate-950">Entrar</h1>
          <p className="mt-3 text-base leading-7 text-slate-700">
            Acesse o monitoramento das armadilhas com a sua conta.
          </p>
        </header>

        {motivoSaida === 'expirou' ? (
          <p
            className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-950"
            role="status"
          >
            Sua sessão expirou. Entre novamente.
          </p>
        ) : null}

        {estado === 'carregando' ? (
          <EstadoCarregando />
        ) : (
          <form
            className="space-y-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-8"
            noValidate
            onSubmit={enviar}
          >
            {erro ? <MensagemErro erro={erro} /> : null}
            <CampoFormulario
              autoComplete="username"
              id="email"
              nome="email"
              obrigatorio
              rotulo="E-mail"
              tipo="email"
            />
            <CampoFormulario
              autoComplete="current-password"
              id="senha"
              nome="senha"
              obrigatorio
              referencia={referenciaSenha}
              rotulo="Senha"
              tipo="password"
            />
            <Botao className="w-full" disabled={enviando} type="submit" variante="primario">
              {enviando ? 'Entrando…' : 'Entrar'}
            </Botao>
            <p className="text-sm leading-6 text-slate-700">
              Esqueceu a senha? Peça ao administrador para redefini-la.
            </p>
          </form>
        )}
      </main>
    </div>
  )
}
