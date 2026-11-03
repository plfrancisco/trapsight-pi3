import { urlImagemAnalise } from '../services/midia'

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
}

/** Mostra somente a foto original enviada para a análise. */
export default function ImagemAnalise({
  analiseId,
  descricao,
  width,
  height,
  imagemClassName,
  moldura,
  loading,
}: ImagemAnaliseProps) {
  const imagem = (
    <img
      alt={`Imagem original ${descricao}`}
      className={imagemClassName}
      decoding="async"
      height={height}
      loading={loading}
      src={urlImagemAnalise(analiseId)}
      width={width}
    />
  )

  return moldura ? <div className={moldura}>{imagem}</div> : imagem
}
