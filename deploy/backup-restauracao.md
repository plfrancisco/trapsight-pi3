# Backup e restauração do PostgreSQL

O banco guarda **dados sensíveis**: hashes de senha Argon2id das contas
(`usuario.senha_hash`), tokens de sessão e as imagens das análises em colunas
`BYTEA` (`analise.imagem_original` e `analise.mascara`, usadas quando
`STORAGE_BACKEND=database`). Um dump é, portanto, uma cópia completa do material
mais sensível do sistema: ele nunca fica em claro fora do momento da restauração,
nunca entra no repositório e nunca é anexado em chat, e-mail ou issue.

O par de scripts cobre o ciclo inteiro:

| Script | Papel |
| --- | --- |
| `scripts/backup-banco.sh` | `pg_dump` no formato custom, cifrado para uma chave pública, com `.sha256` do artefato |
| `scripts/restaurar-banco.sh` | confere o hash, decifra em memória e restaura **em banco vazio** |
| `scripts/testar-restauracao.sh` | prova o ciclo em um PostgreSQL descartável e compara linhas, imagens e login |

## O que o plano gratuito do Supabase cobre

A documentação oficial de backups do Supabase (consultada em 28/10/2026,
<https://supabase.com/docs/guides/platform/backups>) afirma:

- **Backup diário automático** existe para os planos **Pro, Team e
  Enterprise** — "We automatically back up all Pro, Team, and Enterprise Plan
  projects on a daily basis". O plano **gratuito não aparece nessa lista**.
- **Retenção:** Pro, últimos 7 dias; Team, últimos 14 dias; Enterprise, até 30
  dias. Não há janela de retenção publicada para o plano gratuito.
- Para o plano gratuito, a recomendação é explícita: exportar os dados com
  regularidade e **manter cópias fora da plataforma** ("maintain off-site
  backups"), usando o comando `db dump` da CLI do Supabase.
- **Objetos do Storage não entram no backup do banco** — "Database backups do
  not include objects you store via the Storage API". Isso não afeta este
  projeto enquanto as imagens ficarem em `BYTEA` no próprio banco, mas passa a
  afetar no dia em que a mídia migrar para o Storage.
- Restaurar um backup da plataforma **derruba o projeto** durante o processo:
  "The project is inaccessible during this process, so plan for downtime
  beforehand".

Conclusão operacional: **no plano gratuito, o backup é responsabilidade do
projeto**. Point-in-time recovery também não está disponível; o melhor cenário
possível é perder o intervalo desde o último dump gerado por nós.

## Frequência recomendada

Enquanto o sistema for protótipo em demonstração, com dados reinseríveis:

- **Semanal** como rotina mínima, e **antes de cada migração ou deploy** que
  toque schema ou dados — é nesse momento que a perda é mais provável.
- **Diário** a partir do instante em que existirem dados reais de campo que não
  possam ser recriados.
- **Guardar as três últimas cópias** e descartar as anteriores: dump cifrado
  acumulado é superfície de risco, não segurança.
- **Testar a restauração a cada mudança de schema** e, fora disso, pelo menos
  uma vez por mês (`scripts/testar-restauracao.sh`).

## Onde guardar o dump

- **Fora do servidor web.** O backup nunca fica na máquina que atende a
  internet: se ela for comprometida, o backup vai junto. O script recusa
  qualquer `BACKUP_DIR` dentro do repositório e cria o diretório com permissão
  `700`, e os arquivos com `600`.
- **Fora do repositório e fora de qualquer pasta sincronizada em claro.** O
  padrão é `~/backups-trapsight`.
- **Duas localizações**, sendo uma fora da máquina de desenvolvimento (disco
  externo ou armazenamento pessoal). Como o arquivo já vai cifrado, um
  armazenamento de terceiros guarda apenas texto ilegível.
- A **chave privada nunca** acompanha o dump nem entra no repositório: ela mora
  em `~/.trapsight-seguranca/chave_privada.pem`, igual à do relatório cifrado da
  suíte de segurança. Backup e chave no mesmo lugar equivalem a backup em claro.

## Como cifrar

O repositório já tem uma convenção de cifra por chave pública — a mesma do
relatório cego da suíte de segurança: `openssl cms` com o certificado público
`security/cifra/certificado.pem`, decifrável só por quem tem a chave privada
correspondente. O backup usa essa convenção por padrão, sem instalar nada novo:

```bash
BACKUP_DATABASE_URL="postgresql://usuario:senha@host:5432/postgres" \
  scripts/backup-banco.sh
```

O resultado é `~/backups-trapsight/armadilhas-<data>.dump.cms` mais o
`.sha256` do arquivo cifrado — que permite verificar a integridade de uma cópia
arquivada sem precisar da chave privada.

Para cifrar com GPG em vez do CMS, basta informar a chave pública do
destinatário; a extensão passa a ser `.dump.gpg`:

```bash
BACKUP_DATABASE_URL="..." BACKUP_GPG_DESTINATARIO="<id-da-chave>" \
  scripts/backup-banco.sh
```

A conexão é lida **somente do ambiente** (`BACKUP_DATABASE_URL` ou
`DATABASE_URL`). A senha é retirada da URL e passada por `PGPASSWORD`, para não
aparecer na linha de comando do `pg_dump`, visível a outros processos da
máquina; e qualquer mensagem de erro do `pg_dump` passa por um filtro que
substitui URLs antes de ir para a tela. Nenhuma das duas rotas imprime o dump.

Quando `pg_dump` não está no `PATH`, o script o executa na imagem
`postgres:17.6-alpine`. Se o banco só responde dentro de uma rede Docker (o
caso do Compose de produção), informe `BACKUP_DOCKER_REDE`.

## Como testar a restauração

```bash
scripts/testar-restauracao.sh          # cifra CMS (padrão)
TESTE_CIFRA=gpg scripts/testar-restauracao.sh
```

O teste sobe um PostgreSQL próprio (`pi-backup-restauracao-db`), aplica as
migrações, cria um gerente, um operador e análises com imagem, gera o backup,
**destrói o banco**, restaura e compara:

- contagem de linhas de cada tabela, antes e depois;
- tamanho e SHA-256 de cada `imagem_original` e `mascara`, calculados dentro do
  banco;
- um **login real** do gerente com a senha original;
- a recusa da restauração contra um banco que ainda tem tabelas.

Ele não toca o banco de desenvolvimento nem o de produção: contêiner, rede, par
de chaves e diretório do backup são criados e removidos pelo próprio script, e
a chave privada do projeto não participa.

## Como restaurar

O script só aceita um banco **vazio** — restaurar sobre tabelas existentes
mistura dois estados e produz um banco que não corresponde a nenhum dos dois.
A verificação conta as tabelas do schema `public`; os schemas internos do
Supabase (`auth`, `storage`, `extensions`) são ignorados, porque nunca estão
vazios em um projeto gerenciado.

```bash
RESTORE_DATABASE_URL="postgresql://postgres:senha@host:5432/postgres" \
  scripts/restaurar-banco.sh ~/backups-trapsight/armadilhas-<data>.dump.cms
```

O dump é decifrado direto para o `pg_restore`, em uma transação única: nenhuma
cópia em claro toca o disco e uma falha no meio não deixa banco pela metade.

### No Supabase

1. Use a conexão **direta** ou o pooler em modo sessão (porta `5432`) com o
   usuário `postgres`. O pooler transacional (`6543`) não serve a restauração,
   pela mesma razão que não serve a migrações.
2. Em um **projeto novo**, crie antes os papéis que o dump referencia nas
   políticas e permissões, porque eles são do cluster e não vêm no dump:
   ```sql
   CREATE ROLE trapsight_backend NOLOGIN;
   CREATE ROLE trapsight_runtime LOGIN PASSWORD '<senha-gerada>'
     NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
   GRANT trapsight_backend TO trapsight_runtime;
   ```
   A senha é gerada na hora e guardada só no gerenciador de segredos.
3. Confirme que o schema `public` está vazio (projeto recém-criado já está) e
   rode `scripts/restaurar-banco.sh`.
4. Depois da restauração, confira a versão das migrações e um login:
   `SELECT version_num FROM alembic_version;`
5. Atualize a `DATABASE_URL` no Vercel se o host do projeto mudou.

Restaurar **por cima** de um projeto que já está em uso não é suportado por
estes scripts: crie um banco novo, restaure nele e só então aponte a aplicação.

## Limites conhecidos

- O backup cobre **só o banco**. Arquivos sob `UPLOADS_DIR` não entram; com
  `STORAGE_BACKEND=database` as imagens estão no próprio dump, mas em uma
  instalação com backend `filesystem` o diretório de uploads precisa de cópia
  própria.
- Não há agendamento automático: a periodicidade acima depende de alguém
  executar o script (ou de um agendador do sistema operacional, ainda não
  configurado).
- A rotação das cópias antigas é manual.
