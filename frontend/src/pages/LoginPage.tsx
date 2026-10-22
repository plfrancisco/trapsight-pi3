import { useRef, useState, type FormEvent } from 'react'
import { Navigate, useLocation } from 'react-router'
import { useAuth } from '../auth/useAuth'
import Botao from '../components/Botao'
import CampoFormulario from '../components/CampoFormulario'
import EstadoCarregando from '../components/EstadoCarregando'
import MarcaTrapSight from '../components/MarcaTrapSight'
import MensagemErro from '../components/MensagemErro'
import ControleTema from '../components/ControleTema'
import { mensagemDeLogin } from '../lib/autenticacao'
import { destinoDoEstado } from '../lib/destino'
import { useTema } from '../hooks/useTema'

/** Autentica o usuário e o leva ao destino que ele tentava acessar.
 * @returns A tela de login, ou o redirecionamento quando já há sessão.
 */
export default function LoginPage() {
  const { ativa, estado, motivoSaida, login } = useAuth()
  const { tema, alternarTema } = useTema()
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
    <div className="login-page">
      <section aria-label="Sobre o TrapSight" className="login-art">
        <div className="login-art__brand">
          <MarcaTrapSight />
        </div>
        <div className="login-art__copy">
          <p className="login-art__eyebrow">Monitoramento de precisão</p>
          <h2 className="login-art__title">
            Cada ponto,
            <span> acompanhado.</span>
          </h2>
          <p className="login-art__description">
            Reúna imagens, leituras e trocas de refil em um painel feito para orientar a próxima ação.
          </p>
        </div>
        <p className="login-art__footnote">TrapSight · inteligência visual para armadilhas adesivas</p>
      </section>

      <section className="login-form-side">
        <div className="login-form-side__theme">
          <ControleTema onAlternar={alternarTema} tema={tema} />
        </div>
        <main className="login-form-content" id="conteudo-principal">
          <p className="login-form-content__eyebrow">Acesso à plataforma</p>
          <h1>Entrar</h1>
          <p className="login-form-content__intro">
            Acesse o monitoramento das armadilhas com a sua conta.
          </p>

          {motivoSaida === 'expirou' ? (
            <p className="login-expired-message" role="status">
              Sua sessão expirou. Entre novamente.
            </p>
          ) : null}

          {estado === 'carregando' ? (
            <EstadoCarregando />
          ) : (
            <form noValidate onSubmit={enviar}>
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
              <p>
                Esqueceu a senha? Peça ao administrador para redefini-la.
              </p>
            </form>
          )}
        </main>
      </section>
    </div>
  )
}
