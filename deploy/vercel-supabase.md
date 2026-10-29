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
| `INFERENCE_MODE` | `stub` enquanto não houver pesos; o padrão é `modelo` e, sem os pesos, a API não inicia |
| `MODEL_WEIGHTS_PATH` | `/tmp/modelo-inativo` enquanto a inferência usar o stub |
| `MODEL_VERSION` | `v0.1.0-demo` |
| `UPLOADS_DIR` | `/tmp/trapsight` (não usado para mídia com o backend `database`) |
| `STORAGE_BACKEND` | `database` |
| `VITE_API_URL` | `/api` (padrão do frontend) |
| `VITE_AUTENTICACAO_ATIVA` | `true` (padrão em produção) |

Não crie variáveis Supabase com prefixo `VITE_`. A interface não acessa o
Supabase diretamente. O papel de banco do backend não tem acesso por meio dos
papéis `anon` ou `authenticated` e usa políticas RLS próprias.

## Preparação do banco no Supabase (não testado contra Supabase real)

As instruções desta seção e de carregamento do seed abaixo são **não testadas
contra um projeto Supabase real**; valide-as em um projeto de teste antes do
deploy.

As migrações criam o papel de execução sozinhas; só a senha fica de fora, por
não poder ir para o repositório.

1. Rode `alembic upgrade head` com a conexão **direta** ou o pooler em modo
   sessão (porta `5432`) e o usuário administrador `postgres`. Nunca pelo pooler
   transacional (`6543`), que não serve a migrações. A `0007` cria
   `trapsight_backend` (sem login) e habilita RLS nas tabelas; a `0008` cria
   `trapsight_runtime` (com login, sem senha, sem `SUPERUSER`, `CREATEROLE` nem
   `BYPASSRLS`) e lhe concede `trapsight_backend`.
2. No SQL Editor, defina a senha do papel de execução, gerada na hora e guardada
   só no gerenciador de segredos (nunca no repositório nem no chat):
   `ALTER ROLE trapsight_runtime PASSWORD '<senha-gerada>';`
3. Monte a `DATABASE_URL` de produção com o pooler transacional (`6543`) e o
   usuário `trapsight_runtime.<project-ref>`, e cadastre-a no Vercel como
   sensível.
4. Crie o gerente pela CLI, com a senha lida da entrada padrão:
   `python -m src.cli criar-usuario --email <e-mail> --nome <nome> --papel gerente --senha-stdin`.
   A senha do gerente é a definitiva (a CLI não exige troca); os operadores
   criados depois pela tela Contas trocam a senha inicial no primeiro acesso.
5. Confira que o papel não é privilegiado:
   `SELECT rolsuper, rolcreaterole, rolbypassrls FROM pg_roles WHERE rolname = 'trapsight_runtime';`
   deve devolver três `false`.

Em um Supabase novo e vazio, essas etapas se repetem do mesmo jeito; a `0007`
e a `0008` só atuam enquanto o papel administrador puder criar papéis.

## Carregar a demonstração no Supabase (não testado contra Supabase real)

O seed é uma operação manual e explícita. O catálogo de sprites deve ser
mantido fora do repositório e acessível ao processo que executa o comando; o
seed não baixa sprites nem aceita um caminho dentro do checkout. A senha e a
URL devem vir de um gerenciador de segredos ou de variáveis exportadas no
ambiente, nunca de um arquivo versionado ou do histórico do shell.

Com o grupo `treino` instalado, use a conexão direta do Supabase (porta `5432`)
ou o pooler em modo sessão. Não use a porta `6543` para esta operação. O exemplo
abaixo pressupõe que o gerenciador de segredos já exportou
`SUPABASE_DATABASE_URL` com `sslmode=require`, usuário
`trapsight_runtime.<project-ref>` e a senha:

```powershell
cd backend
$env:DATABASE_URL = $env:SUPABASE_DATABASE_URL
$env:STORAGE_BACKEND = "database"
$env:TRAPSIGHT_TRAINING_DATA_DIR = "D:\dados-trapsight\sprites"
$env:UPLOADS_DIR = "D:\Estudos - Pedro\dados-trapsight\seed-uploads"
uv run python -m src.seed_demo --confirmar-ambiente
```

O comando mostra somente o host, a porta e o nome do banco. Em armazenamento
`database`, cada PNG é gravado nas colunas `imagem_original` e `mascara`; o
`UPLOADS_DIR` persistente guarda apenas o manifesto local de propriedade. Não
use `TEMP`: se o manifesto `.seed_demo_manifest.json` sumir, a idempotência e a
prova de propriedade dos registros se perdem; com os cenários ainda no banco,
o seed recusa a reexecução e não os substitui. Reexecuções substituem somente os
seis cenários registrados no manifesto correspondente. Este fluxo continua
**não testado contra Supabase real**.

## Limites da demonstração

O Vercel limita o corpo de uma requisição a 4,5 MiB; por isso a API aceita
imagens de até 4 MiB. A imagem original e a máscara ficam em colunas `BYTEA`
privadas no Supabase, sem depender do disco temporário das funções. Isso é
adequado para a demonstração de baixo volume até dezembro; a cota do banco
gratuito precisa ser acompanhada se forem enviadas muitas análises.

O modelo de visão segue como stub até que os pesos de inferência sejam
distribuídos separadamente. Este deploy não inclui o dataset de treinamento.
