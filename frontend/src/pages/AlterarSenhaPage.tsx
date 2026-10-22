import { useRef, useState, type FormEvent } from 'react'
import { useAuth } from '../auth/useAuth'
import Botao from '../components/Botao'
import CampoFormulario from '../components/CampoFormulario'
import MensagemErro from '../components/MensagemErro'
import {
  SENHA_TAMANHO_MINIMO,
  mensagemDeTrocaSenha,
  validateNovaSenha,
} from '../lib/autenticacao'

/** Permite ao usuário trocar a própria senha.
 * @returns O formulário de troca de senha.
 */
export default function AlterarSenhaPage() {
  const { usuario, changeSenha } = useAuth()
  const referenciaFormulario = useRef<HTMLFormElement>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [concluida, setConcluida] = useState(false)
  const [enviando, setEnviando] = useState(false)

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const formulario = new FormData(evento.currentTarget)
    const atual = String(formulario.get('senha_atual') ?? '')
    const nova = String(formulario.get('senha_nova') ?? '')
    const confirmacao = String(formulario.get('senha_confirmacao') ?? '')

    setConcluida(false)
    if (!atual) {
      setErro('Informe a senha atual.')
      return
    }
    const invalida = validateNovaSenha(nova, confirmacao)
    if (invalida) {
      setErro(invalida)
      return
    }

    setEnviando(true)
    setErro(null)
    try {
      await changeSenha(atual, nova)
      referenciaFormulario.current?.reset()
      setConcluida(true)
    } catch (falha: unknown) {
      setErro(mensagemDeTrocaSenha(falha))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="page-stack mx-auto max-w-xl">
      <header className="page-header">
        <p className="page-kicker">Segurança da conta</p>
        <h1 className="page-title">
          Alterar senha
        </h1>
        <p className="page-description">
          Ao trocar a senha, as suas outras sessões são encerradas.
        </p>
      </header>

      {concluida ? (
        <p
          className="success-message"
          role="status"
        >
          Senha alterada. As outras sessões foram encerradas.
        </p>
      ) : null}

      <form
        className="form-panel space-y-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-8"
        noValidate
        onSubmit={enviar}
        ref={referenciaFormulario}
      >
        {erro ? <MensagemErro erro={erro} /> : null}
        {/* Ajuda os gerenciadores de senha a associar a troca à conta certa. */}
        <input
          aria-hidden="true"
          autoComplete="username"
          className="hidden"
          name="usuario"
          readOnly
          tabIndex={-1}
          type="text"
          value={usuario?.email ?? ''}
        />
        <CampoFormulario
          autoComplete="current-password"
          id="senha-atual"
          nome="senha_atual"
          obrigatorio
          rotulo="Senha atual"
          tipo="password"
        />
        <CampoFormulario
          autoComplete="new-password"
          descricao={`Use ao menos ${SENHA_TAMANHO_MINIMO} caracteres. Uma frase longa funciona bem.`}
          id="senha-nova"
          nome="senha_nova"
          obrigatorio
          rotulo="Nova senha"
          tipo="password"
        />
        <CampoFormulario
          autoComplete="new-password"
          id="senha-confirmacao"
          nome="senha_confirmacao"
          obrigatorio
          rotulo="Confirmar nova senha"
          tipo="password"
        />
        <Botao disabled={enviando} type="submit" variante="primario">
          {enviando ? 'Salvando…' : 'Alterar senha'}
        </Botao>
      </form>
    </div>
  )
}
