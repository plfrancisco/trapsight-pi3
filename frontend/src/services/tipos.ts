/** Valores persistidos pela API; a apresentação aplica os rótulos acentuados. */
export type StatusAnalise = 'ok' | 'atencao' | 'trocar'

/** Resumo do ciclo de refil atualmente instalado. */
export interface RefilAtivo {
  id: string
  data_instalacao: string
  dias_em_uso: number
}

/** Resumo de um ciclo de refil encerrado. */
export interface RefilAnterior {
  id: string
  data_instalacao: string
  data_troca: string
  dias_ate_troca: number
}

/** Armadilha com estado consolidado para o dashboard. */
export interface ArmadilhaLista {
  id: string
  identificador: string
  localizacao: string | null
  modelo: string | null
  modelo_id: string | null
  refil_ativo: RefilAtivo | null
  percentual_atual: number | null
  status: StatusAnalise | null
  dias_ate_saturar: number | null
  ultima_analise_em: string | null
  em_alerta_desde: string | null
}

/** Armadilha com datas de cadastro e histórico de refis. */
export interface ArmadilhaDetalhe {
  id: string
  identificador: string
  modelo: string | null
  modelo_id: string | null
  localizacao: string | null
  data_instalacao: string | null
  removida_em?: string | null
  refil_ativo: RefilAtivo | null
  refis_anteriores: RefilAnterior[]
  percentual_atual: number | null
  status: StatusAnalise | null
  dias_ate_saturar: number | null
}

/** Modelo de armadilha pré-cadastrado pelo fabricante. */
export interface ModeloArmadilha {
  id: string
  codigo: string
  nome: string
  fabricante: string
  descricao: string | null
  atracao: string | null
  refil_largura_mm: number
  refil_altura_mm: number
}

/** Campos aceitos no cadastro de uma armadilha. */
export interface ArmadilhaCriar {
  identificador: string
  modelo_id?: string | null
  localizacao?: string | null
  data_instalacao?: string | null
  criar_refil_inicial?: boolean
}

/** Campos editáveis no cadastro parcial de uma armadilha. */
export interface ArmadilhaAtualizar {
  identificador?: string
  modelo_id?: string | null
  localizacao?: string | null
}

/** Data de instalação do ciclo iniciado por uma troca de refil. */
export interface RefilTrocaCriar {
  data_instalacao: string
}

/** Ciclo de refil encerrado pela troca. */
export interface RefilEncerrado {
  id: string
  data_instalacao: string
  data_troca: string
  dias_ate_troca: number
}

/** Ciclo de refil criado pela troca. */
export interface RefilNovo {
  id: string
  data_instalacao: string
  dias_em_uso: number
}

/** Resultado da troca, com o ciclo anterior quando havia um refil ativo. */
export interface RefilTrocaSaida {
  refil_encerrado: RefilEncerrado | null
  refil_novo: RefilNovo
}

/** Resultado persistido e URL relativa da imagem original. */
export interface Analise {
  id: string
  refil_id: string
  armadilha_id: string
  analisado_em: string
  percentual_coberto: number
  status: StatusAnalise
  modelo_versao: string
  imagem_url: string
}

/** Escopos aceitos pela consulta do histórico de análises. */
export type EscopoHistorico = 'refil_ativo' | 'completo'

/** Filtros opcionais da consulta de análises de uma armadilha. */
export interface FiltrosAnalises {
  escopo?: EscopoHistorico
  refilId?: string
  limite?: number
}

/** Usuário autenticado, como devolvido pela API (sem dados de senha). */
export interface Usuario {
  id: string
  email: string
  nome: string
  papel: 'gerente' | 'operador'
  troca_senha_pendente: boolean
}

/** Campos aceitos ao criar uma conta de operador. */
export interface UsuarioEntrada {
  email: string
  nome: string
  senha: string
}

/** Projeção pública de uma conta administrada pelo gerente. */
export interface Conta extends Omit<Usuario, 'troca_senha_pendente'> {
  ativo: boolean
  ultimo_login_em: string | null
  criado_em: string
}

/** Sessão atual: o usuário e o token CSRF exigido em métodos que alteram estado. */
export interface SessaoAtual {
  usuario: Usuario
  csrf_token: string
}

/** Resultado da troca de senha: a sessão é renovada e traz um novo token CSRF. */
export interface TrocaSenhaSaida {
  csrf_token: string
}
