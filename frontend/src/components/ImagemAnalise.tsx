import { useState } from 'react'
import { urlImagemAnalise, urlMascaraAnalise } from '../services/midia'

interface ImagemAnaliseProps {
  analiseId: string
  /** Complemento do texto alternativo, por exemplo "da análise de 03/11/2026 09:10". */
  descricao: string
  width: number
  height: number
  imagemClassName: string
  /** Classes da moldura em volta da imagem; sem ela a imagem é renderizada sozinha. */
  moldura?: string
  loading?: 'lazy' | 'eager'
  /**
   * `mascara` mostra a foto com a área coberta marcada pelo modelo e volta para a
   * foto original se a máscara não carregar. `original` (padrão) mostra só a foto.
   */
  variante?: 'mascara' | 'original'
  /** Mostra uma linha explicando a cor da marcação enquanto a máscara estiver na tela. */
  legenda?: boolean
}

/** Mostra a imagem de uma análise: a máscara do modelo, com a foto original como reserva. */
export default function ImagemAnalise({
  analiseId,
  descricao,
  width,
  height,
  imagemClassName,
  moldura,
  loading,
  variante = 'original',
  legenda = false,
}: ImagemAnaliseProps) {
  // Guarda a análise cuja máscara falhou: ao trocar de análise a máscara volta a ser tentada.
  const [idSemMascara, setIdSemMascara] = useState<string | null>(null)
  const comMascara = variante === 'mascara' && idSemMascara !== analiseId

  const imagem = (
    <img
      alt={
        comMascara
          ? `Imagem com a máscara do modelo ${descricao}`
          : `Imagem original ${descricao}`
      }
      className={imagemClassName}
      decoding="async"
      height={height}
      loading={loading}
      onError={comMascara ? () => setIdSemMascara(analiseId) : undefined}
      src={comMascara ? urlMascaraAnalise(analiseId) : urlImagemAnalise(analiseId)}
      width={width}
    />
  )
  const conteudo = moldura ? <div className={moldura}>{imagem}</div> : imagem

  if (!legenda || !comMascara) return conteudo
  return (
    <>
      {conteudo}
      <p className="mt-2 flex items-center gap-2 text-xs text-slate-600">
        <span
          aria-hidden="true"
          className="inline-block size-3 rounded-sm bg-fuchsia-500"
        />
        Área coberta da placa, marcada pelo modelo
      </p>
    </>
  )
}
