import { Outlet } from 'react-router'
import MensagemErro from '../components/MensagemErro'
import { useAuth } from './useAuth'

/** Impede montar telas administrativas quando o usuário não é gerente. */
export default function RotaGerente() {
  const { usuario } = useAuth()
  return usuario?.papel === 'gerente'
    ? <Outlet />
    : <MensagemErro erro="Acesso negado. Esta área é restrita ao gerente." />
}
