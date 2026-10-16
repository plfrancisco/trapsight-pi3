import type { ButtonHTMLAttributes } from 'react'
import { classesBotao, type BotaoTamanho, type BotaoVariante } from './botaoStyles'

export type { BotaoTamanho, BotaoVariante } from './botaoStyles'

interface BotaoProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variante: BotaoVariante
  tamanho?: BotaoTamanho
}

/** Renderiza uma ação nativa com foco visível, altura acessível e variante visual.
 * @param props Atributos do botão, conteúdo e variante de apresentação.
 * @returns Um elemento button com os estilos compartilhados.
 */
export default function Botao({
  children,
  className,
  variante,
  tamanho = 'padrao',
  type = 'button',
  ...props
}: BotaoProps) {
  return (
    <button
      className={classesBotao(variante, tamanho, className)}
      type={type}
      {...props}
    >
      {children}
    </button>
  )
}
