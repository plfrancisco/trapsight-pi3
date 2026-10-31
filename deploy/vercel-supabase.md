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
| `INFERENCE_MODE` | `stub` no deploy; o padrão é `modelo` e, sem os pesos, a API não inicia |
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

1. Crie no Supabase um projeto exclusivo para o ambiente. Guarde a senha do
   banco no gerenciador de segredos; selecione uma conexão direta ou pooler de
   sessão com TLS e verifique a conectividade antes de continuar.
2. Exporte `DATABASE_URL` pelo gerenciador de segredos, com o papel de migração
   `postgres`, e rode na pasta `backend` `uv run alembic upgrade head` com a
   conexão **direta** ou o pooler em modo sessão (porta `5432`) e o usuário
   administrador `postgres`. Nunca pelo pooler
   transacional (`6543`), que não serve a migrações. A `0007` cria
   `trapsight_backend` (sem login) e habilita RLS nas tabelas; a `0008` cria
   `trapsight_runtime` (com login, sem senha, sem `SUPERUSER`, `CREATEROLE` nem
   `BYPASSRLS`) e lhe concede `trapsight_backend`.
3. No SQL Editor, defina a senha do papel de execução, gerada na hora e guardada
   só no gerenciador de segredos (nunca no repositório nem no chat):
   `ALTER ROLE trapsight_runtime PASSWORD '<senha-gerada>';`
4. Monte a `DATABASE_URL` de produção com o pooler transacional (`6543`) e o
   usuário `trapsight_runtime.<project-ref>`, e cadastre-a no Vercel como
   sensível.
5. Crie o gerente pela CLI, com a senha lida da entrada padrão:
   `python -m src.cli criar-usuario --email <e-mail> --nome <nome> --papel gerente --senha-stdin`.
   A senha do gerente é a definitiva (a CLI não exige troca); os operadores
   criados depois pela tela Contas trocam a senha inicial no primeiro acesso.
6. Confira que o papel não é privilegiado:
   `SELECT rolsuper, rolcreaterole, rolbypassrls FROM pg_roles WHERE rolname = 'trapsight_runtime';`
   deve devolver três `false`.

Em um Supabase novo e vazio, essas etapas se repetem do mesmo jeito; a `0007`
e a `0008` só atuam enquanto o papel administrador puder criar papéis.

O `head` atual é `0012`: `0001` a `0006` criam os dados, contas, catálogo e
mídias; `0007` cria o papel sem login, concessões DML e políticas RLS; `0008`
cria o login de execução; `0009` protege `alembic_version` com RLS; `0010`
e `0011` acrescentam papéis e troca de senha; `0012` cria auditoria com apenas
SELECT e INSERT para a aplicação. O papel de migração é separado do papel de
execução. As migrações 0007 e 0008 podem pular a criação de papéis se faltar
privilégio: uma execução sem erro não substitui as conferências abaixo.

### Checklist após configurar (não testado contra Supabase real)

Execute as consultas abaixo como administrador no SQL Editor. Não inclua
senhas nos comandos compartilhados ou no histórico. Se alguma conferência
falhar, interrompa a publicação e investigue as concessões e políticas; não
considere a verificação aprovada apenas porque a migration terminou.

```sql
SELECT version_num FROM public.alembic_version;
-- Esperado: 0012.
SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolbypassrls
FROM pg_roles WHERE rolname IN ('trapsight_backend', 'trapsight_runtime');
-- Esperado: dois papéis; só runtime pode fazer login, quatro privilégios false.
SELECT pg_has_role('trapsight_runtime', 'trapsight_backend', 'MEMBER');
-- Esperado: true.
SELECT c.relname, c.relrowsecurity
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') ORDER BY c.relname;
-- Esperado: RLS true em todas as tabelas da aplicação e alembic_version.
SELECT tablename, policyname, roles, cmd FROM pg_policies
WHERE schemaname = 'public' ORDER BY tablename, policyname;
-- Esperado: políticas de acesso do backend; auditoria apenas SELECT e INSERT;
-- nenhuma política permite acesso a anon, authenticated ou PUBLIC.
SELECT c.relname, has_table_privilege('trapsight_runtime', c.oid, 'SELECT') AS sel,
       has_table_privilege('trapsight_runtime', c.oid, 'INSERT') AS ins,
       has_table_privilege('trapsight_runtime', c.oid, 'UPDATE') AS upd,
       has_table_privilege('trapsight_runtime', c.oid, 'DELETE') AS del
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') ORDER BY c.relname;
-- Esperado: DML nas sete tabelas da aplicação; auditoria só SELECT/INSERT.
-- alembic_version não deve ser acessível ao runtime pelas políticas RLS.
```

Para verificar o bloqueio efetivo, repita para `anon` e `authenticated`, em
sessões administrativas separadas, uma transação por tabela abaixo. Substitua
`<PAPEL>` e `<TABELA>` por identificadores fixos, nunca por entrada de usuário:

```sql
BEGIN;
SET LOCAL ROLE <PAPEL>;
SELECT count(*) FROM public.<TABELA>;
ROLLBACK;
```

Em `armadilha`, `refil`, `analise`, `modelo_armadilha`, `usuario`, `sessao`,
`tentativa_login`, `auditoria_cli` e `alembic_version`, espera-se permissão
negada ou zero linhas, inclusive com dados de teste existentes. Após erro,
execute `ROLLBACK` antes da próxima tentativa. Revise também as políticas e
concessões herdadas: RLS restringe linhas, enquanto permissões restringem
operações; verificar só uma delas é insuficiente. Para escrita, faça testes
controlados na homologação descartável e confirme que INSERT, UPDATE e DELETE
são negados ou não afetam linhas, sem dados reais.

Com `psql` conectado pelo papel da aplicação usando TLS, execute
`SELECT current_user, ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid();`:
espera-se o papel de execução e `ssl = true`. No pooler, essa consulta mede
a conexão do pooler ao banco; confirme separadamente que o cliente usa TLS
com `sslmode=require`. Pelo papel de migração, `uv run alembic current`
deve mostrar `0012 (head)`. Crie contas somente por `criar-usuario`; não há
usuário padrão. A senha é recebida por `--senha-stdin` de forma segura.

## Carregar a demonstração no Supabase (não testado contra Supabase real)

O seed é uma operação manual e explícita. O catálogo de sprites deve ser
mantido fora do repositório e acessível ao processo que executa o comando; o
seed não baixa sprites nem aceita um caminho dentro do checkout. A senha e a
URL devem vir de um gerenciador de segredos ou de variáveis exportadas no
ambiente, nunca de um arquivo versionado ou do histórico do shell.

`TRAPSIGHT_TRAINING_DATA_DIR` aponta para a pasta externa com `manifest.json`
ou para sua pasta pai se houver `sprites/manifest.json`. Copie o catálogo
preservando os caminhos relativos e confira contagens e SHA-256 entre origem
e cópia antes de usá-lo. Não envie o banco licenciado ao Git ou ao deploy.
O procedimento local está no [README do backend](../backend/README.md).

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

O deploy usa `INFERENCE_MODE=stub`: o PyTorch (`torch`) e os pesos de 93 MB
não cabem na função Vercel. Como disponibilizar e ativar o modelo real é uma
decisão em aberto. Este deploy não inclui o dataset de treinamento.
