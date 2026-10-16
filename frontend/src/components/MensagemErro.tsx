import { ApiError } from '../services/erros'

interface MensagemErroProps {
  erro: ApiError | string
}

/** Apresenta uma falha em uma região anunciada por tecnologias assistivas. */
export default function MensagemErro({ erro }: MensagemErroProps) {
  const mensagem = erro instanceof ApiError ? erro.mensagem : erro

  return (
    <div
      className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-950"
      role="alert"
    >
      {mensagem}
    </div>
  )
}
