import EstadoVazio from './EstadoVazio'
import LinkBotao from './LinkBotao'

/** Explica que a armadilha não existe e oferece retorno ao dashboard.
 * @returns O estado vazio reutilizável para uma armadilha ausente.
 */
export default function ArmadilhaNaoEncontrada() {
  return (
    <EstadoVazio
      acao={
        <LinkBotao to="/" variante="primario">
          Ir para o dashboard
        </LinkBotao>
      }
      descricao="A armadilha solicitada não existe ou não está mais disponível."
      titulo="Armadilha não encontrada"
    />
  )
}
