import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useReproducao } from '../hooks/useReproducao'
import { buildResumoCobertura, buildSerieCobertura } from '../lib/cobertura'
import { formatDataHora, formatPercentual } from '../lib/formatacao'
import {
  instanteDoQuadro,
  instantesTroca,
  mapearArrastoParaIndice,
  VELOCIDADE_PADRAO_MS,
} from '../lib/timelapse'
import { ApiError } from '../services/erros'
import { listAnalises } from '../services/analises'
import { urlImagemAnalise, urlMascaraAnalise } from '../services/midia'
import type { Analise, RefilAnterior } from '../services/tipos'
import Botao from './Botao'
import ControlesTimelapse, { type EscopoTimelapse } from './ControlesTimelapse'
import EstadoCarregando from './EstadoCarregando'
import EstadoVazio from './EstadoVazio'
import MensagemErro from './MensagemErro'
import QuadroTimelapse from './QuadroTimelapse'

const EvolucaoGrafico = lazy(() => import('./EvolucaoGrafico'))

interface TimelapseProps {
  armadilhaId: string
  analisesAtivas: Analise[]
  refisAnteriores: RefilAnterior[]
}

function ordenarAnalises(analises: readonly Analise[]): Analise[] {
  return [...analises].sort(
    (analiseA, analiseB) =>
      Date.parse(analiseA.analisado_em) - Date.parse(analiseB.analisado_em),
  )
}

function ImagemAnaliseUnica({ analise }: { analise: Analise }) {
  const dataHora = formatDataHora(analise.analisado_em)
  const percentual = formatPercentual(analise.percentual_coberto)

  return (
    <figure className="surface-panel overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <img
        alt={`Imagem da armadilha registrada em ${dataHora}, com ${percentual} de cobertura`}
        className="max-h-[34rem] w-full bg-slate-50 object-contain"
        decoding="async"
        height={480}
        src={urlImagemAnalise(analise.id)}
        width={640}
      />
      <figcaption className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-200 px-4 py-3 text-sm text-slate-700 sm:px-5">
        <span>{dataHora}</span>
        <span className="font-semibold text-slate-950">Cobertura: {percentual}</span>
      </figcaption>
    </figure>
  )
}

/** Sincroniza os quadros de análise com o marcador temporal do gráfico.
 * @param props Armadilha, análises ativas carregadas e refis encerrados.
 * @returns Controles de escopo, quadro atual, série e reprodução sincronizada.
 */
export default function Timelapse({
  armadilhaId,
  analisesAtivas,
  refisAnteriores,
}: TimelapseProps) {
  const [escopo, setEscopo] = useState<EscopoTimelapse>('refil_ativo')
  const [velocidadeMs, setVelocidadeMs] = useState(VELOCIDADE_PADRAO_MS)
  const [historicoCompleto, setHistoricoCompleto] = useState<Analise[] | null>(null)
  const [carregandoCompleto, setCarregandoCompleto] = useState(false)
  const [erroCompleto, setErroCompleto] = useState<unknown | null>(null)
  const [tentativaCompleta, setTentativaCompleta] = useState(0)
  const imagensPrecarregadas = useRef<HTMLImageElement[]>([])

  const analisesEscopo = useMemo(
    () => ordenarAnalises(
      escopo === 'refil_ativo'
        ? analisesAtivas
        : historicoCompleto ?? [],
    ),
    [analisesAtivas, escopo, historicoCompleto],
  )
  const instantes = useMemo(
    () => analisesEscopo.map((analise) => Date.parse(analise.analisado_em)),
    [analisesEscopo],
  )
  const marcasDeTroca = useMemo(
    () => escopo === 'completo' ? instantesTroca(refisAnteriores) : [],
    [escopo, refisAnteriores],
  )
  const serie = useMemo(() => buildSerieCobertura(analisesEscopo), [analisesEscopo])
  const resumo = useMemo(() => buildResumoCobertura(analisesEscopo), [analisesEscopo])
  const {
    indiceQuadro,
    reproduzindo,
    playTimelapse,
    pauseTimelapse,
    changeQuadro,
  } = useReproducao(analisesEscopo.length, velocidadeMs)
  const indiceVisivel = Math.max(
    0,
    Math.min(analisesEscopo.length - 1, indiceQuadro),
  )
  const analiseAtual = analisesEscopo[indiceVisivel]

  useEffect(() => {
    if (tentativaCompleta === 0 || historicoCompleto !== null) return

    let requisicaoAtiva = true

    void listAnalises(armadilhaId, { escopo: 'completo', limite: 1000 })
      .then((analises) => {
        if (requisicaoAtiva) setHistoricoCompleto(analises)
      })
      .catch((erro: unknown) => {
        if (requisicaoAtiva) setErroCompleto(erro)
      })
      .finally(() => {
        if (requisicaoAtiva) setCarregandoCompleto(false)
      })

    return () => {
      requisicaoAtiva = false
    }
  }, [armadilhaId, historicoCompleto, tentativaCompleta])

  useEffect(() => {
    if (!analiseAtual) {
      imagensPrecarregadas.current = []
      return
    }

    const proximasAnalises = analisesEscopo.slice(indiceVisivel + 1, indiceVisivel + 3)
    const urls = proximasAnalises.flatMap((analise) => [
      urlImagemAnalise(analise.id),
      urlMascaraAnalise(analise.id),
    ])
    imagensPrecarregadas.current = urls.map((url) => {
      const imagem = new Image()
      imagem.src = url
      return imagem
    })
  }, [analiseAtual, analisesEscopo, indiceVisivel])

  function loadCompleto() {
    if (historicoCompleto !== null || carregandoCompleto) return
    setErroCompleto(null)
    setCarregandoCompleto(true)
    setTentativaCompleta((tentativa) => tentativa + 1)
  }

  function changeEscopo(novoEscopo: EscopoTimelapse) {
    if (novoEscopo === escopo) return
    changeQuadro(0)
    setEscopo(novoEscopo)
    if (novoEscopo === 'completo' && tentativaCompleta === 0) loadCompleto()
  }

  const changeMarcador = useCallback(
    (instante: number) => {
      const indice = mapearArrastoParaIndice(instantes, instante)
      if (indice >= 0) changeQuadro(indice)
    },
    [changeQuadro, instantes],
  )

  const togglePlayback = useCallback(() => {
    if (reproduzindo) pauseTimelapse()
    else playTimelapse()
  }, [pauseTimelapse, playTimelapse, reproduzindo])

  const possuiTimelapse = analisesEscopo.length >= 2

  function abrirHistorico() {
    changeEscopo('completo')
    if (historicoCompleto === null) loadCompleto()
  }

  if (analisesAtivas.length === 0) return null

  return (
    <section
      aria-label={possuiTimelapse ? undefined : 'Imagem da análise da armadilha'}
      aria-labelledby={possuiTimelapse ? 'titulo-evolucao' : undefined}
      className="space-y-4"
    >
      {possuiTimelapse ? (
        <>
          <div>
            <p className="section-kicker">
              {escopo === 'refil_ativo' ? 'Refil ativo' : 'Histórico completo'}
            </p>
            <h2 className="section-title" id="titulo-evolucao">
              Evolução da cobertura
            </h2>
          </div>

          <ControlesTimelapse
            escopo={escopo}
            indiceQuadro={indiceVisivel}
            quantidade={analisesEscopo.length}
            reproduzindo={reproduzindo}
            velocidadeMs={velocidadeMs}
            onChangeEscopo={changeEscopo}
            onChangeQuadro={changeQuadro}
            onChangeVelocidade={setVelocidadeMs}
            onTogglePlayback={togglePlayback}
          />

          {analiseAtual ? (
            <>
              <QuadroTimelapse
                analise={analiseAtual}
                indice={indiceVisivel}
                quantidade={analisesEscopo.length}
                reproduzindo={reproduzindo}
              />
              <Suspense fallback={<div aria-live="polite" className="h-80" role="status">Carregando gráfico…</div>}>
                <EvolucaoGrafico
                  marcasDeTroca={marcasDeTroca}
                  marcador={instanteDoQuadro(instantes, indiceVisivel) ?? undefined}
                  onInteracaoManual={pauseTimelapse}
                  onMarcadorChange={changeMarcador}
                  resumo={resumo}
                  serie={serie}
                />
              </Suspense>
            </>
          ) : null}
        </>
      ) : (
        <>
          {escopo === 'refil_ativo' && analiseAtual ? (
            <ImagemAnaliseUnica analise={analiseAtual} />
          ) : null}

          {escopo === 'completo' && carregandoCompleto ? <EstadoCarregando /> : null}
          {escopo === 'completo' && erroCompleto ? (
            <div className="space-y-3">
              <MensagemErro
                erro={
                  erroCompleto instanceof ApiError
                    ? erroCompleto
                    : 'Não foi possível carregar o histórico completo.'
                }
              />
              <div className="flex flex-wrap gap-3">
                <Botao onClick={loadCompleto} variante="primario">
                  Tentar novamente
                </Botao>
                <Botao onClick={() => changeEscopo('refil_ativo')} variante="secundario">
                  Voltar ao refil ativo
                </Botao>
              </div>
            </div>
          ) : null}

          {escopo === 'completo' && !carregandoCompleto && !erroCompleto && analiseAtual ? (
            <>
              <ImagemAnaliseUnica analise={analiseAtual} />
              <Botao onClick={() => changeEscopo('refil_ativo')} variante="secundario">
                Voltar ao refil ativo
              </Botao>
            </>
          ) : null}

          {escopo === 'completo' && !carregandoCompleto && !erroCompleto && !analiseAtual ? (
            <div className="space-y-3">
              <EstadoVazio
                descricao="Não há análises disponíveis neste histórico."
                titulo="Nenhuma análise neste histórico"
              />
              <Botao onClick={() => changeEscopo('refil_ativo')} variante="secundario">
                Voltar ao refil ativo
              </Botao>
            </div>
          ) : null}

          {escopo === 'refil_ativo' && refisAnteriores.length > 0 ? (
            <div className="surface-panel flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
              <p className="text-sm text-slate-700">
                Consulte as análises dos refis anteriores para comparar os ciclos.
              </p>
              <Botao onClick={abrirHistorico} variante="secundario">
                Ver histórico completo
              </Botao>
            </div>
          ) : null}
        </>
      )}
    </section>
  )
}
