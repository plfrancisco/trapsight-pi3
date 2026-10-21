import { BrowserRouter, Route, Routes } from 'react-router'
import AuthProvider from './auth/AuthProvider'
import RotaProtegida from './auth/RotaProtegida'
import Layout from './components/Layout'
import AlterarSenhaPage from './pages/AlterarSenhaPage'
import CadastroArmadilhaPage from './pages/CadastroArmadilhaPage'
import DashboardPage from './pages/DashboardPage'
import DetalheArmadilhaPage from './pages/DetalheArmadilhaPage'
import LoginPage from './pages/LoginPage'
import NaoEncontradaPage from './pages/NaoEncontradaPage'
import NovaAnalisePage from './pages/NovaAnalisePage'

/**
 * Declara as rotas para permitir testes com qualquer router. Só `/login` é pública;
 * todas as demais (inclusive a página 404, para não revelar rotas a quem não entrou)
 * ficam atrás da exigência de sessão.
 */
export function Rotas() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RotaProtegida />}>
        <Route element={<Layout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/armadilhas/nova" element={<CadastroArmadilhaPage />} />
          <Route path="/armadilhas/:id" element={<DetalheArmadilhaPage />} />
          <Route path="/armadilhas/:id/editar" element={<CadastroArmadilhaPage />} />
          <Route path="/analises/nova" element={<NovaAnalisePage />} />
          <Route path="/conta/senha" element={<AlterarSenhaPage />} />
          <Route path="*" element={<NaoEncontradaPage />} />
        </Route>
      </Route>
    </Routes>
  )
}

/** Monta a navegação declarativa e o estado de autenticação da aplicação. */
function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Rotas />
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
