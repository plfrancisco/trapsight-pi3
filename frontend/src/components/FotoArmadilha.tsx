import { useState } from 'react'
import { imagemDoModelo } from '../lib/modeloImagem'
import { urlAbsoluta } from '../services/midia'
import type { FotoTipo } from '../services/tipos'

interface FotoArmadilhaProps {
  identificador: string
  modelo: string | null
  fotoTipo: FotoTipo
  fotoUrl: string | null
  className?: string
}

/** Mostra a foto da armadilha: a real enviada pelo usuário ou a padrão do modelo.
 * Se a foto real não carregar, volta sozinha à foto padrão em vez de ficar quebrada.
 * @param props Dados de identificação e a origem da foto informada pela API.
 * @returns A imagem, ou um quadro de reserva quando nem o modelo tem foto.
 */
export default function FotoArmadilha({
  identificador,
  modelo,
  fotoTipo,
  fotoUrl,
  className,
}: FotoArmadilhaProps) {
  const [fotoRealFalhou, setFotoRealFalhou] = useState(false)
  const imagemModelo = imagemDoModelo(modelo)
  const usaFotoReal = fotoTipo === 'real' && fotoUrl !== null && !fotoRealFalhou

  if (usaFotoReal) {
    return (
      <img
        alt={`Foto da armadilha ${identificador}`}
        className={className}
        decoding="async"
        loading="lazy"
        onError={() => setFotoRealFalhou(true)}
        src={urlAbsoluta(fotoUrl)}
      />
    )
  }
  if (imagemModelo) {
    return (
      <img
        alt={`Foto padrão do modelo ${modelo ?? 'de armadilha'}`}
        className={className}
        decoding="async"
        loading="lazy"
        src={imagemModelo}
      />
    )
  }
  return (
    <div className="trap-photo-placeholder" role="img" aria-label={`Sem foto da armadilha ${identificador}`}>
      <p>Sem foto disponível</p>
    </div>
  )
}
