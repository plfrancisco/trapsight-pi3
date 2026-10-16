import { BrowserRouter, Route, Routes } from 'react-router'
import Layout from './components/Layout'
import CadastroArmadilhaPage from './pages/CadastroArmadilhaPage'
import DashboardPage from './pages/DashboardPage'
import DetalheArmadilhaPage from './pages/DetalheArmadilhaPage'
import NaoEncontradaPage from './pages/NaoEncontradaPage'
import NovaAnalisePage from './pages/NovaAnalisePage'

/** Declara as rotas dentro do layout compartilhado para permitir testes com qualquer router. */
export function Rotas() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/armadilhas/nova" element={<CadastroArmadilhaPage />} />
        <Route path="/armadilhas/:id" element={<DetalheArmadilhaPage />} />
        <Route path="/armadilhas/:id/editar" element={<CadastroArmadilhaPage />} />
        <Route path="/analises/nova" element={<NovaAnalisePage />} />
        <Route path="*" element={<NaoEncontradaPage />} />
      </Route>
    </Routes>
  )
}

/** Monta a navegação declarativa da aplicação no histórico do navegador. */
function App() {
  return (
    <BrowserRouter>
      <Rotas />
    </BrowserRouter>
  )
}

export default App
