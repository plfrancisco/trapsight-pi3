import { useEffect, useMemo, type ChangeEvent } from 'react'
import { validateArquivoAnalise } from '../lib/analise'
import { urlAbsoluta } from '../services/midia'
import type { FotoTipo } from '../services/tipos'
import Botao from './Botao'

export type ModoFoto = FotoTipo

interface CampoFotoArmadilhaProps {
  modo: ModoFoto
  arquivo: File | null
  /** URL relativa da foto real já gravada, quando a armadilha está em edição. */
  fotoAtualUrl: string | null
  erro: string | null
  onModoChange: (modo: ModoFoto) => void
  onArquivoChange: (arquivo: File | null, erro: string | null) => void
}

/** Escolhe entre a foto padrão do modelo e uma foto real da armadilha.
 * Valida tipo e tamanho antes do envio e mostra a pré-visualização do arquivo.
 * @param props Escolha atual, arquivo selecionado e callbacks do formulário.
 * @returns O grupo de campos de foto do cadastro e da edição.
 */
export default function CampoFotoArmadilha({
  modo,
  arquivo,
  fotoAtualUrl,
  erro,
  onModoChange,
  onArquivoChange,
}: CampoFotoArmadilhaProps) {
  const previa = useMemo(
    () => (arquivo ? URL.createObjectURL(arquivo) : null),
    [arquivo],
  )

  useEffect(() => {
    return () => {
      if (previa) URL.revokeObjectURL(previa)
    }
  }, [previa])

  const escolherArquivo = (evento: ChangeEvent<HTMLInputElement>) => {
    const escolhido = evento.target.files?.[0] ?? null
    if (!escolhido) {
      onArquivoChange(null, null)
      return
    }
    const problema = validateArquivoAnalise(escolhido)
    onArquivoChange(problema ? null : escolhido, problema)
    if (problema) evento.target.value = ''
  }

  const imagemExibida = previa ?? (fotoAtualUrl ? urlAbsoluta(fotoAtualUrl) : null)

  return (
    <fieldset className="space-y-3">
      <legend className="text-sm font-semibold text-slate-900">Foto da armadilha</legend>
      <label className="flex min-h-11 cursor-pointer items-center gap-3 text-sm text-slate-900">
        <input
          checked={modo === 'padrao'}
          className="size-5 accent-emerald-900"
          name="foto_modo"
          onChange={() => onModoChange('padrao')}
          type="radio"
          value="padrao"
        />
        <span>Foto padrão do modelo</span>
      </label>
      <label className="flex min-h-11 cursor-pointer items-center gap-3 text-sm text-slate-900">
        <input
          checked={modo === 'real'}
          className="size-5 accent-emerald-900"
          name="foto_modo"
          onChange={() => onModoChange('real')}
          type="radio"
          value="real"
        />
        <span>Foto real da armadilha</span>
      </label>

      {modo === 'real' ? (
        <div className="space-y-3 pl-8">
          <div>
            <label className="text-sm font-medium text-slate-800" htmlFor="foto-arquivo">
              Arquivo da foto
            </label>
            <input
              accept="image/jpeg,.jpg,.jpeg,image/png,.png"
              aria-describedby={erro ? 'foto-erro' : 'foto-ajuda'}
              aria-invalid={erro ? true : undefined}
              className="mt-1 block w-full text-sm"
              id="foto-arquivo"
              onChange={escolherArquivo}
              type="file"
            />
            <p className="mt-1 text-sm text-slate-700" id="foto-ajuda">
              JPEG ou PNG, até 4 MB. A imagem é reduzida e os metadados (como a
              localização do celular) são descartados.
            </p>
            {erro ? (
              <p className="mt-1 text-sm font-medium text-red-800" id="foto-erro" role="alert">
                {erro}
              </p>
            ) : null}
          </div>
          {imagemExibida ? (
            <div className="photo-field__preview">
              <img
                alt={previa ? 'Pré-visualização da nova foto' : 'Foto atual da armadilha'}
                src={imagemExibida}
              />
            </div>
          ) : null}
          <Botao onClick={() => onModoChange('padrao')} variante="discreto">
            Voltar à foto padrão
          </Botao>
        </div>
      ) : null}
    </fieldset>
  )
}
