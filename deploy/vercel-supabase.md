# Deploy de demonstração: Vercel Services + Supabase

O Vercel Services publica a interface Vite (`frontend/`) e a API FastAPI
(`backend/`) em um único projeto e domínio. As requisições do navegador em
`/api/*` são encaminhadas para o backend; as demais rotas públicas vão para o
frontend, incluindo o fallback de rotas do React. O navegador não recebe chave
Supabase: o backend conecta ao PostgreSQL pelo pooler de transações do Supabase,
com SSL e uma conta de banco dedicada.

O frontend usa `/api` como endereço padrão da API na mesma origem. Em
desenvolvimento, `VITE_API_URL` pode continuar apontando para a API local.
Não há binding entre os serviços: a chamada acontece no navegador pela rota
pública `/api`, e o backend acessa o Supabase diretamente. A pasta `security/`
contém ferramentas de teste e pentest, não um serviço HTTP; ela não é publicada
como serviço Vercel.

## Variáveis de produção no Vercel

Cadastre apenas no ambiente Production. Marque `DATABASE_URL` como sensível.

| Variável | Valor |
| --- | --- |
| `DATABASE_URL` | URL do pooler transacional, porta `6543`, usuário `trapsight_runtime.<project-ref>`, `sslmode=require` |
| `AMBIENTE` | `producao` |
| `COOKIE_SECURE` | `true` |
| `CORS_ORIGENS` | Origem HTTPS oficial do projeto Vercel |
| `MODEL_WEIGHTS_PATH` | `/tmp/modelo-inativo` enquanto a inferência usar o stub |
| `MODEL_VERSION` | `v0.1.0-demo` |
| `UPLOADS_DIR` | `/tmp/trapsight` (não usado para mídia com o backend `database`) |
| `STORAGE_BACKEND` | `database` |
| `VITE_API_URL` | `/api` (padrão do frontend) |
| `VITE_AUTENTICACAO_ATIVA` | `true` (padrão em produção) |

Não crie variáveis Supabase com prefixo `VITE_`. A interface não acessa o
Supabase diretamente. O papel de banco do backend não tem acesso por meio dos
papéis `anon` ou `authenticated` e usa políticas RLS próprias.

## Limites da demonstração

O Vercel limita o corpo de uma requisição a 4,5 MiB; por isso a API aceita
imagens de até 4 MiB. A imagem original e a máscara ficam em colunas `BYTEA`
privadas no Supabase, sem depender do disco temporário das funções. Isso é
adequado para a demonstração de baixo volume até dezembro; a cota do banco
gratuito precisa ser acompanhada se forem enviadas muitas análises.

O modelo de visão segue como stub até que os pesos de inferência sejam
distribuídos separadamente. Este deploy não inclui o dataset de treinamento.
