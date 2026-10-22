/** Apresenta o título e a orientação inicial da tela de análise.
 * @returns O cabeçalho da tela Nova análise.
 */
export default function CabecalhoNovaAnalise() {
  return (
    <header className="page-header">
      <p className="page-kicker">
        Processamento de imagem
      </p>
      <h1 className="page-title">
        Nova análise
      </h1>
      <p className="page-description">
        Envie uma foto da superfície adesiva para medir a cobertura e consultar
        o resultado do modelo.
      </p>
    </header>
  )
}
