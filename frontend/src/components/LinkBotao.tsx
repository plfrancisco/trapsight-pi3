import { Link, type LinkProps } from 'react-router'
import { classesBotao, type BotaoTamanho, type BotaoVariante } from './botaoStyles'

interface LinkBotaoProps extends LinkProps {
  variante: BotaoVariante
  tamanho?: BotaoTamanho
  className?: string
}

/** Renderiza um link de navegação com apresentação e foco consistentes com Botao.
 * @param props Destino, conteúdo e variante visual do link.
 * @returns Um elemento âncora gerenciado pelo roteador.
 */
export default function LinkBotao({
  children,
  className,
  variante,
  tamanho = 'padrao',
  ...props
}: LinkBotaoProps) {
  return (
    <Link
      className={classesBotao(variante, tamanho, className)}
      {...props}
    >
      {children}
    </Link>
  )
}
