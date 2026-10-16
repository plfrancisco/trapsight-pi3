import type { ReactNode } from 'react'
import { useCallback } from 'react'
import { useParams } from 'react-router'
import ArmadilhaNaoEncontrada from '../components/ArmadilhaNaoEncontrada'
import Botao from '../components/Botao'
import EstadoCarregando from '../components/EstadoCarregando'
import FormularioArmadilha from '../components/FormularioArmadilha'
import MensagemErro from '../components/MensagemErro'
import { useCarregamento } from '../hooks/useCarregamento'
import { ApiError } from '../services/erros'
import { getArmadilha } from '../services/armadilhas'
import type { ArmadilhaDetalhe } from '../services/tipos'

function CabecalhoEdicao() {
  return (
    <h1 className="text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">
      Editar armadilha
    </h1>
  )
}

function EstadoEdicao({ children }: { children: ReactNode }) {
  return (
    <div className="space-y-5">
      <CabecalhoEdicao />
      {children}
    </div>
  )
}

/** Carrega os dados de edição e apresenta falhas antes do formulário.
 * @returns A tela de cadastro ou um estado de carregamento/erro.
 */
export default function CadastroArmadilhaPage() {
  const { id } = useParams()
  const loadArmadilha = useCallback(
    (signal: AbortSignal) =>
      id ? getArmadilha(id, signal) : Promise.resolve<ArmadilhaDetalhe | null>(null),
    [id],
  )
  const {
    dados,
    erro,
    carregando,
    recarregar: reload,
  } = useCarregamento(loadArmadilha)

  if (!id) {
    return <FormularioArmadilha dados={null} />
  }

  if (carregando) {
    return (
      <EstadoEdicao>
        <EstadoCarregando />
      </EstadoEdicao>
    )
  }

  if (erro instanceof ApiError && erro.codigo === 'ARMADILHA_NAO_ENCONTRADA') {
    return (
      <EstadoEdicao>
        <ArmadilhaNaoEncontrada />
      </EstadoEdicao>
    )
  }

  if (erro) {
    return (
      <EstadoEdicao>
        <MensagemErro
          erro={
            erro instanceof ApiError
              ? erro
              : 'Não foi possível carregar os dados da armadilha.'
          }
        />
        <Botao onClick={reload} variante="primario">
          Tentar novamente
        </Botao>
      </EstadoEdicao>
    )
  }

  return <FormularioArmadilha dados={dados} id={id} />
}
