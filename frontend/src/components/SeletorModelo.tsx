import type { ModeloArmadilha } from '../services/tipos'

interface SeletorModeloProps {
  modelos: ModeloArmadilha[]
  /** Modelo marcado ao abrir o formulário. */
  valorPadrao: string | null
  erro?: string | null
  onChange?: () => void
}

/** Apresenta os modelos do fabricante como opções de escolha única. */
export default function SeletorModelo({
  modelos,
  valorPadrao,
  erro,
  onChange,
}: SeletorModeloProps) {
  return (
    <fieldset
      aria-describedby={erro ? 'modelo-erro' : undefined}
      className="space-y-3"
    >
      <legend className="text-sm font-semibold text-app-foreground">
        Modelo da armadilha <span aria-hidden="true">*</span>
      </legend>
      <div className="grid gap-3 sm:grid-cols-2">
        {modelos.map((modelo) => (
          <label
            className="flex min-h-11 cursor-pointer gap-3 rounded-xl border border-app-border bg-app-surface p-4 has-[:checked]:border-app-primary has-[:checked]:bg-app-soft has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-app-primary"
            key={modelo.id}
          >
            <input
              className="mt-1 size-5 accent-emerald-900"
              defaultChecked={modelo.id === valorPadrao}
              name="modelo_id"
              onChange={onChange}
              type="radio"
              value={modelo.id}
            />
            <span className="space-y-1">
              <span className="block text-base font-semibold text-app-foreground">
                {modelo.nome}
              </span>
              <span className="block text-sm text-app-muted">
                Fabricante {modelo.fabricante}
                {modelo.atracao ? ` · Atração ${modelo.atracao}` : ''}
              </span>
              <span className="block text-sm text-app-muted">
                Refil {modelo.refil_largura_mm} × {modelo.refil_altura_mm} mm
              </span>
              {modelo.descricao ? (
                <span className="block text-sm leading-5 text-app-muted">
                  {modelo.descricao}
                </span>
              ) : null}
            </span>
          </label>
        ))}
      </div>
      {erro ? (
        <p className="text-sm font-medium text-red-800" id="modelo-erro">
          {erro}
        </p>
      ) : null}
    </fieldset>
  )
}
