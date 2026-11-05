import {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useState,
  type ReactNode,
} from 'react'
import { AUTENTICACAO_ATIVA } from '../config'
import { useInatividade } from '../hooks/useInatividade'
import {
  CHAVE_SESSAO,
  gravarCache,
  lerCache,
  limparCacheUsuario,
} from '../lib/cacheLocal'
import { estaInativo, lerUltimaAtividade, registrarAtividade } from '../lib/inatividade'
import * as api from '../services/auth'
import { ApiError } from '../services/erros'
import {
  assinarSessaoExpirada,
  assinarTrocaObrigatoria,
  definirCsrf,
  limparCsrf,
} from '../services/sessao'
import type { Usuario } from '../services/tipos'
import {
  AuthContexto,
  type AuthContextoValor,
  type EstadoAuth,
  type MotivoSaida,
} from './contexto'

interface SituacaoAuth {
  estado: EstadoAuth
  usuario: Usuario | null
  motivoSaida: MotivoSaida
  /** Verdadeiro enquanto o usuário vem do cache local e o servidor ainda não confirmou a sessão. */
  provisoria: boolean
}

/** O mínimo guardado para desenhar a tela antes de o servidor responder. */
interface DicaDeSessao {
  id: string
  nome: string
  papel: Usuario['papel']
}

function ehDicaDeSessao(valor: unknown): valor is DicaDeSessao {
  if (typeof valor !== 'object' || valor === null) return false
  const dica = valor as Record<string, unknown>
  return (
    typeof dica.id === 'string'
    && typeof dica.nome === 'string'
    && (dica.papel === 'gerente' || dica.papel === 'operador')
  )
}

/** Define como o aplicativo começa: sem sessão conhecida, já logado pelo cache ou deslogado por inatividade. */
function situacaoInicial(ativa: boolean): { situacao: SituacaoAuth; inativoAoAbrir: boolean } {
  if (!ativa) {
    return {
      situacao: { estado: 'autenticado', usuario: null, motivoSaida: null, provisoria: false },
      inativoAoAbrir: false,
    }
  }

  if (estaInativo(lerUltimaAtividade())) {
    return {
      situacao: { estado: 'anonimo', usuario: null, motivoSaida: 'inativo', provisoria: false },
      inativoAoAbrir: true,
    }
  }

  const dica = lerCache(CHAVE_SESSAO, ehDicaDeSessao)
  if (dica) {
    return {
      situacao: {
        estado: 'autenticado',
        usuario: { ...dica, email: '', troca_senha_pendente: false },
        motivoSaida: null,
        provisoria: true,
      },
      inativoAoAbrir: false,
    }
  }

  return {
    situacao: { estado: 'carregando', usuario: null, motivoSaida: null, provisoria: false },
    inativoAoAbrir: false,
  }
}

type Acao =
  | { tipo: 'carregando' }
  | { tipo: 'sessao'; usuario: Usuario }
  | { tipo: 'anonimo' }
  | { tipo: 'erro' }
  | { tipo: 'saiu' }
  | { tipo: 'expirou' }
  | { tipo: 'inativo' }
  | { tipo: 'troca_pendente' }

function reduzir(situacao: SituacaoAuth, acao: Acao): SituacaoAuth {
  switch (acao.tipo) {
    case 'carregando':
      return { ...situacao, estado: 'carregando', provisoria: false }
    case 'sessao':
      return { estado: 'autenticado', usuario: acao.usuario, motivoSaida: null, provisoria: false }
    case 'anonimo':
      // Um usuário vindo do cache que o servidor não reconhece é uma sessão que expirou.
      return situacao.provisoria
        ? { estado: 'anonimo', usuario: null, motivoSaida: 'expirou', provisoria: false }
        : { ...situacao, estado: 'anonimo', usuario: null }
    case 'erro':
      // Sem rede, quem abriu pelo cache continua vendo o que já tinha.
      return situacao.provisoria ? situacao : { ...situacao, estado: 'erro' }
    case 'troca_pendente':
      return situacao.usuario
        ? { ...situacao, usuario: { ...situacao.usuario, troca_senha_pendente: true } }
        : situacao
    case 'saiu':
      return { estado: 'anonimo', usuario: null, motivoSaida: 'saiu', provisoria: false }
    case 'inativo':
      return { estado: 'anonimo', usuario: null, motivoSaida: 'inativo', provisoria: false }
    case 'expirou':
      // Só importa se havia sessão: no início, um 401 é apenas "ainda não entrou".
      return situacao.estado === 'autenticado'
        ? { estado: 'anonimo', usuario: null, motivoSaida: 'expirou', provisoria: false }
        : situacao
  }
}

interface AuthProviderProps {
  children: ReactNode
  /** Substitui a chave global de autenticação (usado em testes). */
  ativa?: boolean
}

/** Mantém o estado de autenticação e o disponibiliza ao aplicativo.
 * @param props Conteúdo e, opcionalmente, o liga/desliga da autenticação.
 * @returns O provedor do contexto de autenticação.
 */
export default function AuthProvider({
  children,
  ativa = AUTENTICACAO_ATIVA,
}: AuthProviderProps) {
  const [inicio] = useState(() => situacaoInicial(ativa))
  const [situacao, dispatch] = useReducer(reduzir, inicio.situacao)
  const [tentativa, setTentativa] = useState(0)

  // Aberto depois de 20 min parado: revoga a sessão no servidor (best effort) e apaga o cache.
  useEffect(() => {
    if (!inicio.inativoAoAbrir) return
    limparCacheUsuario()
    api
      .getSessao()
      .then((sessao) => {
        definirCsrf(sessao.csrf_token)
        return api.logout()
      })
      .catch(() => undefined)
      .finally(limparCsrf)
  }, [inicio.inativoAoAbrir])

  // Recupera a sessão ao abrir o aplicativo (e a cada nova tentativa).
  useEffect(() => {
    if (!ativa || inicio.inativoAoAbrir) return
    const controlador = new AbortController()

    api
      .getSessao(controlador.signal)
      .then((sessao) => {
        definirCsrf(sessao.csrf_token)
        dispatch({ tipo: 'sessao', usuario: sessao.usuario })
      })
      .catch((falha: unknown) => {
        if (controlador.signal.aborted) return
        limparCsrf()
        dispatch(
          falha instanceof ApiError && falha.status === 401
            ? { tipo: 'anonimo' }
            : { tipo: 'erro' },
        )
      })

    return () => controlador.abort()
  }, [ativa, inicio.inativoAoAbrir, tentativa])

  // O cache de dados acompanha a sessão: guarda a dica quando confirmada, apaga ao deslogar.
  useEffect(() => {
    if (!ativa) return
    if (situacao.estado === 'anonimo') {
      limparCacheUsuario()
    } else if (situacao.estado === 'autenticado' && situacao.usuario && !situacao.provisoria) {
      const { id, nome, papel } = situacao.usuario
      gravarCache<DicaDeSessao>(CHAVE_SESSAO, { id, nome, papel })
    }
  }, [ativa, situacao])

  const expirarPorInatividade = useCallback(() => {
    // O CSRF é lido no início da chamada, antes de ser esquecido logo abaixo.
    void api.logout().catch(() => undefined)
    limparCsrf()
    dispatch({ tipo: 'inativo' })
  }, [])

  const renovarSessao = useCallback(() => {
    // Falhas de rede são ignoradas; um 401 já é tratado pela camada HTTP.
    void api
      .getSessao()
      .then((sessao) => definirCsrf(sessao.csrf_token))
      .catch(() => undefined)
  }, [])

  useInatividade(
    ativa && situacao.estado === 'autenticado',
    expirarPorInatividade,
    renovarSessao,
  )

  // Qualquer resposta "NAO_AUTENTICADO" da API encerra a sessão local.
  useEffect(
    () =>
      assinarSessaoExpirada(() => {
        limparCsrf()
        dispatch({ tipo: 'expirou' })
      }),
    [],
  )

  const login = useCallback(async (email: string, senha: string) => {
    const sessao = await api.login(email, senha)
    // Dados de outra conta que tenham ficado no aparelho não podem aparecer para esta.
    limparCacheUsuario()
    registrarAtividade()
    definirCsrf(sessao.csrf_token)
    dispatch({ tipo: 'sessao', usuario: sessao.usuario })
  }, [])

  useEffect(
    () => assinarTrocaObrigatoria(() => dispatch({ tipo: 'troca_pendente' })),
    [],
  )

  const logout = useCallback(async () => {
    try {
      await api.logout()
    } catch (falha: unknown) {
      // Se a sessão já não existia no servidor, sair está concluído.
      if (!(falha instanceof ApiError && falha.status === 401)) throw falha
    }
    limparCsrf()
    dispatch({ tipo: 'saiu' })
  }, [])

  const changeSenha = useCallback(async (senhaAtual: string, senhaNova: string) => {
    const renovada = await api.changeSenha(senhaAtual, senhaNova)
    definirCsrf(renovada.csrf_token)
    try {
      const sessao = await api.getSessao()
      dispatch({ tipo: 'sessao', usuario: sessao.usuario })
    } catch (falha: unknown) {
      // A senha já mudou; uma falha de consulta deve pedir nova verificação,
      // sem sugerir ao usuário que repita a troca com a senha anterior.
      if (falha instanceof ApiError && falha.status === 401) {
        limparCsrf()
        dispatch({ tipo: 'anonimo' })
      } else {
        dispatch({ tipo: 'erro' })
      }
    }
  }, [])

  const recarregarSessao = useCallback(() => {
    dispatch({ tipo: 'carregando' })
    setTentativa((valor) => valor + 1)
  }, [])

  const valor = useMemo<AuthContextoValor>(
    () => ({
      ativa,
      estado: situacao.estado,
      usuario: situacao.usuario,
      motivoSaida: situacao.motivoSaida,
      login,
      logout,
      changeSenha,
      recarregarSessao,
    }),
    [ativa, situacao, login, logout, changeSenha, recarregarSessao],
  )

  return <AuthContexto.Provider value={valor}>{children}</AuthContexto.Provider>
}
