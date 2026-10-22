import type { ReactNode } from 'react'
import type { ArmadilhaLista } from '../services/tipos'
import Botao from './Botao'
import EstadoCarregando from './EstadoCarregando'
import EstadoVazio from './EstadoVazio'
import LinkBotao from './LinkBotao'
import MensagemErro from './MensagemErro'
import { ApiError } from '../services/erros'

interface SeletorArmadilhaProps {
  armadilhas: ArmadilhaLista[] | null
  carregando: boolean
  erro: unknown
  onRetry: () => void
  children: ReactNode
}

/** Apresenta estados da lista antes de liberar a seleção de uma armadilha.
 * @param props Dados da consulta, ação para repeti-la e formulário carregado.
 * @returns O estado de consulta ou o conteúdo de seleção.
 */
export default function SeletorArmadilha({
  armadilhas,
  carregando,
  erro,
  onRetry,
  children,
}: SeletorArmadilhaProps) {
  if (carregando) {
    return (
      <section aria-labelledby="titulo-formulario-analise" className="space-y-5">
        <h2 className="section-title" id="titulo-formulario-analise">
          Preparando envio
        </h2>
        <EstadoCarregando />
      </section>
    )
  }

  if (erro) {
    return (
      <section aria-labelledby="titulo-formulario-analise" className="space-y-5">
        <h2 className="section-title" id="titulo-formulario-analise">
          Seleção da armadilha
        </h2>
        <MensagemErro
          erro={
            erro instanceof ApiError
              ? erro
              : 'Não foi possível carregar as armadilhas.'
          }
        />
        <Botao onClick={onRetry} variante="primario">
          Tentar novamente
        </Botao>
      </section>
    )
  }

  if (armadilhas?.length === 0) {
    return (
      <EstadoVazio
        acao={
          <LinkBotao to="/armadilhas/nova" variante="primario">
            Cadastrar armadilha
          </LinkBotao>
        }
        descricao="Cadastre uma armadilha antes de iniciar uma análise."
        titulo="Nenhuma armadilha cadastrada"
      />
    )
  }

  return <>{children}</>
}
