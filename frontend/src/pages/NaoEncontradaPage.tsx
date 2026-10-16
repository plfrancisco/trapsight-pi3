/** Informa que o endereço solicitado não corresponde a uma tela disponível. */
export default function NaoEncontradaPage() {
  return (
    <>
      <h1 className="text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">
        Página não encontrada
      </h1>
      <p className="mt-3 max-w-2xl text-base leading-7 text-slate-700">
        O endereço solicitado não corresponde a uma página disponível.
      </p>
    </>
  )
}
