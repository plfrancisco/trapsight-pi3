import type {
  ChangeEventHandler,
  FormEventHandler,
} from 'react'
import { Link } from 'react-router'
import type { ArmadilhaLista } from '../services/tipos'
import BarraProgressoAnalise from './BarraProgressoAnalise'
import Botao from './Botao'
import MensagemErro from './MensagemErro'

interface EnvioAnaliseProps {
  armadilhas: ArmadilhaLista[]
  armadilhaId: string
  armadilhaSelecionada: ArmadilhaLista | null
  arquivo: File | null
  erroArquivo: string | null
  erroAnalise: string | null
  enviando: boolean
  /** A resposta chegou e a barra está indo a 100% antes de mostrar o resultado. */
  concluindo?: boolean
  onChangeArmadilha: ChangeEventHandler<HTMLSelectElement>
  onChangeArquivo: ChangeEventHandler<HTMLInputElement>
  onCancel: () => void
  onSubmit: FormEventHandler<HTMLFormElement>
  timeoutUploadMs: number
}

/** Seleciona a armadilha, valida o arquivo e controla o envio da análise.
 * @param props Dados atuais do fluxo e ações oferecidas pelo formulário.
 * @returns O formulário completo para iniciar uma análise.
 */
export default function EnvioAnalise({
  armadilhas,
  armadilhaId,
  armadilhaSelecionada,
  arquivo,
  erroArquivo,
  erroAnalise,
  enviando,
  concluindo = false,
  onChangeArmadilha,
  onChangeArquivo,
  onCancel,
  onSubmit,
  timeoutUploadMs,
}: EnvioAnaliseProps) {
  const semRefilAtivo = armadilhaSelecionada?.refil_ativo === null

  return (
    <form
      className="form-panel space-y-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-8"
      onSubmit={onSubmit}
    >
      {erroAnalise ? <MensagemErro erro={erroAnalise} /> : null}

      <div className="space-y-2">
        <label className="block text-sm font-semibold text-slate-900" htmlFor="armadilha-id">
          Armadilha
        </label>
        <select
          className="min-h-12 w-full rounded-xl border border-slate-300 bg-white px-3.5 py-3 text-base text-slate-950 shadow-sm focus-visible:border-emerald-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-800 disabled:cursor-not-allowed disabled:bg-slate-100"
          disabled={enviando}
          id="armadilha-id"
          onChange={onChangeArmadilha}
          value={armadilhaId}
        >
          <option value="">Selecione uma armadilha</option>
          {armadilhas.map((armadilha) => (
            <option key={armadilha.id} value={armadilha.id}>
              {armadilha.identificador} — {armadilha.localizacao ?? 'Localização não informada'}
              {armadilha.refil_ativo ? '' : ' — sem refil ativo'}
            </option>
          ))}
        </select>
      </div>

      {semRefilAtivo && armadilhaSelecionada ? (
        <p className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-950">
          Esta armadilha está sem refil ativo. Registre um refil para liberar
          novas análises.{' '}
          <Link
            className="font-semibold underline decoration-amber-800 underline-offset-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-900"
            to={`/armadilhas/${armadilhaSelecionada.id}`}
          >
            Abrir armadilha
          </Link>
        </p>
      ) : null}

      <div className="space-y-2">
        <label className="block text-sm font-semibold text-slate-900" htmlFor="arquivo-imagem">
          Imagem da armadilha
        </label>
        <input
          accept="image/jpeg,.jpg,.jpeg,image/png,.png"
          aria-describedby={erroArquivo ? 'erro-arquivo-imagem' : 'ajuda-arquivo-imagem'}
          aria-invalid={erroArquivo ? true : undefined}
          className="min-h-12 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-800 file:mr-4 file:min-h-9 file:cursor-pointer file:rounded-lg file:border-0 file:bg-emerald-50 file:px-3 file:font-semibold file:text-emerald-950 hover:file:bg-emerald-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-800 disabled:cursor-not-allowed disabled:bg-slate-100"
          disabled={enviando}
          id="arquivo-imagem"
          name="imagem"
          onChange={onChangeArquivo}
          type="file"
        />
        {erroArquivo ? (
          <p
            className="text-sm font-medium text-red-800"
            id="erro-arquivo-imagem"
            role="alert"
          >
            {erroArquivo}
          </p>
        ) : (
          <p className="text-sm leading-5 text-slate-700" id="ajuda-arquivo-imagem">
            JPEG ou PNG, até 4 MB. A API ainda verifica o conteúdo real e a
            resolução da imagem.
          </p>
        )}
        {arquivo && !erroArquivo ? (
          <p className="text-sm text-slate-700">Arquivo selecionado: {arquivo.name}</p>
        ) : null}
      </div>

      {enviando ? (
        <div className="space-y-3 rounded-xl bg-emerald-50 p-4">
          <BarraProgressoAnalise concluido={concluindo} />
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs leading-5 text-emerald-900">
              O processamento pode levar até {timeoutUploadMs / 1000} segundos.
            </p>
            {concluindo ? null : (
              <Botao onClick={onCancel} variante="secundario">
                Cancelar envio
              </Botao>
            )}
          </div>
        </div>
      ) : null}

      <div className="border-t border-slate-200 pt-5">
        <Botao
          disabled={
            enviando ||
            !armadilhaSelecionada ||
            semRefilAtivo ||
            !arquivo ||
            Boolean(erroArquivo)
          }
          tamanho="amplo"
          type="submit"
          variante="primario"
        >
          {enviando ? 'Analisando…' : 'Enviar para análise'}
        </Botao>
      </div>
    </form>
  )
}
