/** Apresenta o título e a orientação inicial da tela de análise.
 * @returns O cabeçalho da tela Nova análise.
 */
export default function CabecalhoNovaAnalise() {
  return (
    <header>
      <p className="text-sm font-semibold uppercase tracking-[0.14em] text-emerald-900">
        Processamento de imagem
      </p>
      <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">
        Nova análise
      </h1>
      <p className="mt-3 max-w-2xl text-base leading-7 text-slate-700">
        Envie uma foto da superfície adesiva para medir a cobertura e consultar
        o resultado do modelo.
      </p>
    </header>
  )
}
