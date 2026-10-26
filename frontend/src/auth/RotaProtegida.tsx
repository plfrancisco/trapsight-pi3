import { Navigate, Outlet, useLocation } from 'react-router'
import Botao from '../components/Botao'
import EstadoCarregando from '../components/EstadoCarregando'
import MensagemErro from '../components/MensagemErro'
import { useAuth } from './useAuth'

/** Exige sessão para as rotas filhas; sem ela, leva ao login e volta depois.
 * @returns As rotas filhas, o estado de carga/erro ou o redirecionamento ao login.
 */
export default function RotaProtegida() {
  const { ativa, estado, usuario, motivoSaida, recarregarSessao } = useAuth()
  const localizacao = useLocation()

  if (
    ativa && estado === 'autenticado' && usuario?.troca_senha_pendente
    && localizacao.pathname !== '/conta/senha'
  ) {
    return <Navigate replace to="/conta/senha" />
  }

  if (!ativa || estado === 'autenticado') return <Outlet />

  // Não exibe nada protegido nem redireciona enquanto não se sabe se há sessão.
  if (estado === 'carregando') {
    return (
      <div className="mx-auto max-w-md px-4 py-16">
        <EstadoCarregando />
      </div>
    )
  }

  if (estado === 'erro') {
    return (
      <div className="mx-auto max-w-md space-y-4 px-4 py-16">
        <MensagemErro erro="Não foi possível verificar sua sessão. Verifique a conexão e tente novamente." />
        <Botao onClick={recarregarSessao} variante="primario">
          Tentar novamente
        </Botao>
      </div>
    )
  }

  // Quem acabou de sair por vontade própria não volta à página anterior depois de entrar.
  const destino =
    motivoSaida === 'saiu' ? undefined : localizacao.pathname + localizacao.search
  return <Navigate replace state={{ destino }} to="/login" />
}
