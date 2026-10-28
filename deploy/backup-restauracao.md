# Backup e restauração do PostgreSQL

O banco guarda **dados sensíveis**: hashes de senha Argon2id das contas
(`usuario.senha_hash`), tokens de sessão e as imagens das análises em colunas
`BYTEA` (`analise.imagem_original` e `analise.mascara`, usadas quando
`STORAGE_BACKEND=database`). Um dump é, portanto, uma cópia completa do material
mais sensível do sistema: ele nunca fica em claro fora do momento da
restauração, nunca entra no repositório e nunca é anexado em chat, e-mail ou
issue.

O par de scripts cobre o ciclo inteiro:

| Script | Papel |
| --- | --- |
| `scripts/backup-banco.sh` | `pg_dump` do schema `public` no formato custom, cifrado para uma chave pública, com `.sha256` do artefato |
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
  em `~/.trapsight-backup/chave_privada.pem`. Backup e chave no mesmo lugar
  equivalem a backup em claro.

## O par de chaves do backup

A cifra segue a convenção que o repositório já usa para o relatório cego da
suíte de segurança — `openssl cms` com certificado público —, mas com **chave
própria**: quem pode abrir um backup não precisa poder abrir os relatórios, e
vice-versa. São dois arquivos com destinos opostos:

| Arquivo | Onde fica |
| --- | --- |
| `security/cifra/backup-certificado.pem` (público) | no repositório; é com ele que o backup é cifrado |
| `chave_privada.pem` (privada) | **só** em `~/.trapsight-backup/`, nunca no repositório |

> **Perder a chave privada é perder todos os backups.** Nenhum dump cifrado com
> ela pode ser aberto de outra forma — não existe recuperação. Guarde uma
> **cópia de segurança da chave privada** em lugar separado dos dumps
> (gerenciador de senhas com anexo, ou mídia offline guardada fisicamente), e
> nunca no mesmo diretório, disco ou nuvem em que os backups são arquivados:
> quem obtiver os dois tem o banco em claro.

Gere o par uma única vez, com validade longa — o certificado só serve para
transportar a chave pública, não há cadeia de confiança envolvida:

```bash
mkdir -p ~/.trapsight-backup && chmod 700 ~/.trapsight-backup
openssl req -x509 -newkey rsa:4096 -nodes -days 3650 \
  -subj "/CN=trapsight-backup" \
  -keyout ~/.trapsight-backup/chave_privada.pem \
  -out security/cifra/backup-certificado.pem
chmod 600 ~/.trapsight-backup/chave_privada.pem
```

No Git Bash, o `openssl` nativo do Windows não entende caminhos `/c/...`:
envolva cada caminho em `$(cygpath -m ...)` ou rode o comando no WSL.

Commite **apenas** `security/cifra/backup-certificado.pem`. A chave privada não
entra no repositório em nenhuma circunstância; se isso acontecer por engano, ela
está comprometida e o par precisa ser trocado, com novo backup de tudo.

## Como cifrar

Com o certificado público no lugar, o backup é um comando:

```bash
BACKUP_DATABASE_URL="postgresql://usuario:senha@host:5432/postgres" \
  scripts/backup-banco.sh
```

O resultado é `~/backups-trapsight/armadilhas-<data>.dump.cms` mais o
`.sha256` do arquivo cifrado — que permite verificar a integridade de uma cópia
arquivada sem precisar da chave privada.

O dump cobre **só o schema `public`** (`pg_dump --schema=public`), onde estão as
tabelas da aplicação e o controle de versão das migrações. Os schemas da
plataforma do Supabase (`auth`, `storage`, `extensions`) ficam de fora: eles
pertencem ao provedor, o papel da aplicação não conseguiria restaurá-los e a
presença deles tornaria o dump incompatível com a exigência de restaurar em
banco vazio, já que em um projeto gerenciado esses schemas nunca estão vazios.
Donos e permissões são preservados, por isso o banco de destino precisa ter os
papéis `trapsight_backend` e `trapsight_runtime`.

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

A restauração usa `pg_restore --schema=public`, que é o par necessário do
`--schema=public` do backup: ao delimitar o schema, o dump passa a carregar um
`CREATE SCHEMA public`, e esse schema já existe em qualquer banco recém-criado.
O filtro aplica os objetos de dentro do schema e ignora a criação dele. Se um
dos dois lados mudar, o outro precisa mudar junto.

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

- O backup cobre **só o schema `public` do banco**. Nada que viva em outro
  schema entra no dump; se algum dia a aplicação passar a criar objetos fora do
  `public`, o `--schema=public` de `scripts/backup-banco.sh` precisa acompanhar.
- Arquivos sob `UPLOADS_DIR` não entram; com
  `STORAGE_BACKEND=database` as imagens estão no próprio dump, mas em uma
  instalação com backend `filesystem` o diretório de uploads precisa de cópia
  própria.
- Não há agendamento automático: a periodicidade acima depende de alguém
  executar o script (ou de um agendador do sistema operacional, ainda não
  configurado).
- A rotação das cópias antigas é manual.
- A guarda da chave privada e da cópia de segurança dela é manual: sem essa
  cópia, um disco perdido invalida de uma vez todos os backups já arquivados.
