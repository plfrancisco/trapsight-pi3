import { useState } from 'react'
import { urlImagemAnalise, urlMascaraAnalise } from '../services/midia'
import Botao from './Botao'

interface ImagemAnaliseProps {
  analiseId: string
  /** Complemento do texto alternativo, por exemplo "da análise de 03/11/2026 09:10". */
  descricao: string
  width: number
  height: number
  imagemClassName: string
  /** Classes da moldura em volta da imagem; sem ela a imagem é renderizada sozinha. */
  moldura?: string
  /** Mostra o botão para alternar entre a identificação do modelo e a foto original. */
  permitirAlternar?: boolean
  /** Mostra a legenda da cor da máscara enquanto ela está visível. */
  mostrarLegenda?: boolean
  loading?: 'lazy' | 'eager'
}

/** Mostra a imagem da análise com a identificação do modelo e, se faltar, a foto enviada.
 *
 * A máscara (`/mascara`) é a própria foto com a área coberta por insetos pintada de
 * magenta. Análises antigas ou feitas sem máscara respondem 404: nesse caso a foto
 * original (`/imagem`) aparece sozinha, sem erro visível e sem nova tentativa.
 * @param props Identificador da análise, texto alternativo e opções de exibição.
 * @returns A imagem, a legenda da cor e o botão de alternância, conforme as opções.
 */
export default function ImagemAnalise({
  analiseId,
  descricao,
  width,
  height,
  imagemClassName,
  moldura,
  permitirAlternar = false,
  mostrarLegenda = true,
  loading,
}: ImagemAnaliseProps) {
  const [mascaraIndisponivel, setMascaraIndisponivel] = useState(false)
  const [verOriginal, setVerOriginal] = useState(false)
  const mostrandoMascara = !mascaraIndisponivel && !verOriginal

  const imagem = (
    <img
      alt={
        mostrandoMascara
          ? `Identificação do modelo na imagem ${descricao}`
          : `Imagem original ${descricao}`
      }
      className={imagemClassName}
      decoding="async"
      height={height}
      loading={loading}
      onError={() => {
        if (mostrandoMascara) setMascaraIndisponivel(true)
      }}
      src={mostrandoMascara ? urlMascaraAnalise(analiseId) : urlImagemAnalise(analiseId)}
      width={width}
    />
  )

  const comLegenda = mostrandoMascara && mostrarLegenda
  const comBotao = permitirAlternar && !mascaraIndisponivel

  return (
    <>
      {moldura ? <div className={moldura}>{imagem}</div> : imagem}
      {comLegenda || comBotao ? (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          {comLegenda ? (
            <p className="flex items-center gap-2 text-sm text-slate-700">
              <span
                aria-hidden="true"
                className="inline-block size-4 shrink-0 rounded border border-fuchsia-700"
                style={{ backgroundColor: 'rgba(255, 0, 255, 0.4)' }}
              />
              Área marcada: cobertura por insetos identificada pelo modelo
            </p>
          ) : (
            <span />
          )}
          {comBotao ? (
            <Botao
              aria-pressed={verOriginal}
              onClick={() => setVerOriginal((atual) => !atual)}
              tamanho="compacto"
              variante="secundario"
            >
              {verOriginal ? 'Ver identificação do modelo' : 'Ver foto original'}
            </Botao>
          ) : null}
        </div>
      ) : null}
    </>
  )
}
