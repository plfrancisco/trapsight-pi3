import { useCallback, useRef, useState, type FormEvent } from 'react'
import Botao from '../components/Botao'
import CampoFormulario from '../components/CampoFormulario'
import AcaoExcluirConta from '../components/AcaoExcluirConta'
import EstadoCarregando from '../components/EstadoCarregando'
import MensagemErro from '../components/MensagemErro'
import { useCarregamento } from '../hooks/useCarregamento'
import { createUsuario, listUsuarios, mensagemDeContas } from '../services/usuarios'

function exibirData(valor: string | null): string {
  return valor
    ? new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(valor))
    : 'Nunca'
}

/** Lista contas e permite ao gerente criar e excluir operadores. */
export default function ContasPage() {
  const carregar = useCallback((signal: AbortSignal) => listUsuarios(signal), [])
  const { dados, erro, carregando, recarregar } = useCarregamento(carregar)
  const formularioRef = useRef<HTMLFormElement>(null)
  const [enviando, setEnviando] = useState(false)
  const [erroCriacao, setErroCriacao] = useState<string | null>(null)
  const [sucesso, setSucesso] = useState(false)
  const [sucessoExclusao, setSucessoExclusao] = useState(false)

  async function criar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (enviando) return
    const form = new FormData(evento.currentTarget)
    const email = String(form.get('email') ?? '').trim()
    const nome = String(form.get('nome') ?? '').trim()
    const senha = String(form.get('senha') ?? '')
    setErroCriacao(null)
    setSucesso(false)
    if (!email || !nome || !senha) {
      setErroCriacao('Preencha o nome, o e-mail e a senha inicial.')
      return
    }
    setEnviando(true)
    try {
      await createUsuario({ email, nome, senha })
      formularioRef.current?.reset()
      setSucesso(true)
      recarregar()
    } catch (falha: unknown) {
      setErroCriacao(mensagemDeContas(falha))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="page-stack">
      <header className="page-header">
        <h1 className="page-title">Contas</h1>
        <p className="page-description">Gerencie o acesso da equipe ao TrapSight.</p>
      </header>
      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <section aria-labelledby="contas-titulo" className="min-w-0 rounded-2xl border border-app-border bg-app-surface p-5">
          <h2 className="mb-4 text-lg font-semibold text-app-foreground" id="contas-titulo">Pessoas com acesso</h2>
          {sucessoExclusao ? <p className="success-message mb-4" role="status">Conta excluída.</p> : null}
          {carregando ? <EstadoCarregando /> : erro ? (
            <div className="space-y-4">
              <MensagemErro erro={mensagemDeContas(erro)} />
              <Botao onClick={recarregar} variante="primario">Tentar novamente</Botao>
            </div>
          ) : dados?.length ? (
            <div className="overflow-x-auto">
              <table className="accounts-table w-full text-left text-sm">
                <caption className="sr-only">Contas cadastradas</caption>
                <thead className="border-b border-app-border text-app-muted">
                  <tr>
                    {['Pessoa', 'Papel', 'Situação', 'Último login', 'Criada em'].map((titulo) => <th className="px-3 py-3 font-medium" key={titulo} scope="col">{titulo}</th>)}
                    <th className="px-3 py-3 font-medium" scope="col">Ações</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-app-border text-app-foreground">
                  {dados.map((conta) => (
                    <tr key={conta.id}>
                      <td className="px-3 py-4"><p className="font-semibold">{conta.nome}</p><p className="break-all text-app-muted">{conta.email}</p></td>
                      <td data-label="Papel" className="px-3 py-4">{conta.papel === 'gerente' ? 'Gerente' : 'Operador'}</td>
                      <td data-label="Situação" className="px-3 py-4">{conta.ativo ? 'Ativa' : 'Desativada'}</td>
                      <td data-label="Último login" className="whitespace-nowrap px-3 py-4">{exibirData(conta.ultimo_login_em)}</td>
                      <td data-label="Criada em" className="whitespace-nowrap px-3 py-4">{exibirData(conta.criado_em)}</td>
                      <td data-label="Ações" className="px-3 py-4">
                        {conta.papel === 'operador' ? (
                          <AcaoExcluirConta
                            email={conta.email}
                            nome={conta.nome}
                            onExcluida={() => {
                              setSucessoExclusao(true)
                              recarregar()
                            }}
                            usuarioId={conta.id}
                          />
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="text-app-muted">Nenhuma conta cadastrada.</p>}
        </section>
        <section aria-labelledby="criar-operador-titulo" className="form-panel rounded-2xl border border-app-border bg-app-surface p-5">
          <h2 className="text-lg font-semibold text-app-foreground" id="criar-operador-titulo">Criar operador</h2>
          <p className="mt-2 text-sm leading-6 text-app-muted">Defina uma senha inicial. A pessoa deverá trocá-la ao entrar.</p>
          {sucesso ? <p className="success-message mt-4" role="status">Conta criada. Compartilhe a senha inicial por um canal seguro.</p> : null}
          <form aria-label="Criar operador" className="mt-6 space-y-5" noValidate onSubmit={(evento) => void criar(evento)} ref={formularioRef}>
            {erroCriacao ? <MensagemErro erro={erroCriacao} /> : null}
            <CampoFormulario id="conta-nome" nome="nome" placeholder="Ex.: Ana Silva…" rotulo="Nome" autoComplete="name" obrigatorio />
            <CampoFormulario id="conta-email" nome="email" placeholder="Ex.: ana@empresa.com…" rotulo="E-mail" tipo="email" autoComplete="off" obrigatorio />
            <CampoFormulario id="conta-senha" nome="senha" rotulo="Senha inicial" tipo="password" autoComplete="new-password" descricao="Use ao menos 8 caracteres, com letras e números, e evite palavras ligadas à conta." obrigatorio />
            <Botao disabled={enviando} type="submit" variante="primario">{enviando ? 'Criando…' : 'Criar operador'}</Botao>
          </form>
        </section>
      </div>
    </div>
  )
}
