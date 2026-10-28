# CURRENT TASK — AUTENTICAÇÃO E HOSPEDAGEM — Projeto Integrador

**Versão:** 1.0
**Status:** ATIVA
**Escopo:** login, proteção da API, hospedagem pública e verificação de segurança antes da publicação

---

# 1. Objetivo

Colocar o protótipo **online e acessível** com autenticação segura, **nada
exposto além do necessário** (portas 80 e 443 no Compose local; no ambiente
publicado, só HTTPS e os controles do Supabase) e a suíte de invasão verde,
conforme `../plan/foundation/login.md` (aprovado em 2026-10-16).

---

# 2. Escopo

Cobre a implementação do login no backend e no frontend, a infraestrutura de
produção e todo o ciclo de verificação de segurança. Não cobre MFA, papel
somente leitura, recuperação de senha por e-mail nem provedor de identidade externo
(Fase 2, `login.md`, seção 12.3). A escolha do provedor de hospedagem foi
concluída (`completed/current_task_externo.md`, EXT04): Vercel e Supabase, sem
domínio comprado nem VPS paga.

**Regras que valem para todas as tasks deste arquivo:**

- **Nada fica aberto** (`login.md`, 1.1 e 10.5): nenhum `ports:` além do proxy,
  banco nunca alcançável de fora, nenhuma rota de dados sem sessão.
- **Execução cega** (`../validation/seguranca_testes.md`, seção 11): quem
  implementa só **executa** a suíte por `security/scans/executar_cego.sh`; o
  relatório sai cifrado e só o revisor o abre. Correções voltam como violações
  da especificação, nunca como saída de teste.
- **A suíte é o critério de aceite.** Antes da implementação ela falha de
  propósito; cada task faz os testes correspondentes passarem. É proibido
  alterar teste ou script para melhorar o resultado.
- Nenhuma credencial, segredo ou `.env` real no repositório
  (`../rules/security_spec.md`, seção 3). Sem usuário nem senha padrão.
- Dependência nova (`pwdlib[argon2]` e as de produção) exige confirmação
  prévia (`../rules/ai_development_rules.md`, regra 4.2).

---

# 3. Tarefas

**Estado (2026-10-26):** AUTH00 a AUTH07 e HOST01 concluídas; HOST02 tem um item
aberto (backup). A publicação ainda não foi feita. O deploy previsto usa Vercel
Services (frontend e API no mesmo projeto e domínio) e Supabase (PostgreSQL pelo
pooler transacional, porta 6543, TLS e papel dedicado), conforme
`../../deploy/vercel-supabase.md`; o Compose de produção com Caddy serve às
varreduras locais.

**Decisão (2026-10-26):** no ambiente publicado, a segurança do banco fica a cargo
dos controles do próprio Supabase (TLS obrigatório, papel dedicado de menor
privilégio, RLS e nenhuma chave Supabase no navegador). A exigência de só as portas
80 e 443 abertas e do banco inalcançável de fora vale para o Compose local, onde o
projeto controla a rede; HOST03 e SEG05 e a seção 5 foram ajustados a isso.

## AUTH00 — Alinhar a especificação

- [x] `rules/security_spec.md`: seção 4 deixa de ser "risco aceito" e aponta
      para `login.md`; ajustar 2.1, 2.3 e 10.3
- [x] `plan/foundation/project_overview.md`: autenticação sai de "fora de
      escopo" (5.2) e entra como requisito da hospedagem
- [x] `plan/foundation/tech_stack.md`: deploy (Caddy + Compose de produção) e a
      dependência `pwdlib[argon2]`
- [x] `plan/api/api_spec.md`: endpoints `/api/auth/*`, os seis códigos de erro
      novos, cabeçalho `X-CSRF-Token` e cookie de sessão
- [x] `plan/data/data_model.md`: tabelas `usuario`, `sessao` e `tentativa_login`
- [x] `plan/frontend/telas_spec.md`: tela `/login`, logout e sessão expirada
- [x] `README.md`: execução, hospedagem e status
- [x] Referências remanescentes a "sem autenticação": `rules/ai_development_rules.md`
      (9.5), `task/completed/current_task_frontend.md` (escopo) e `plan/README.md` (índice)

**Especificação:** `../plan/foundation/login.md`, seção 13.
**Executor:** revisor (é especificação, não código).
**Dependências:** nenhuma. **Precede** todas as demais.
**Concluída em:** 2026-10-16.

## AUTH01 — Dados de usuário e sessão

- [x] Migrations de `usuario`, `sessao` e `tentativa_login` (colunas de
      `login.md`, 5.1 e 7.1), com restrições e índices no banco
- [x] Entidades e repositórios (flush apenas, a rota confirma), sem expor
      `senha_hash` nem `token_hash` em nenhuma projeção de leitura pública
- [x] Dois papéis no banco: **migração** (DDL) e **aplicação** (somente DML), sem
      `SUPERUSER`, `CREATEDB`, `CREATEROLE` (`login.md`, 10.6)
- [x] Senha do banco por ambiente, forte e vinda de variável de ambiente

**Especificação:** `login.md`, 5.1, 7.1 e 10.6.
**Dependências:** AUTH00.
**Verifica:** `security/pentest/test_12_banco_e_hash.py`.

## AUTH02 — Senhas

- [x] Hash com Argon2id (`pwdlib[argon2]`), parâmetros iguais ou acima do mínimo
      do OWASP, configuráveis
- [x] Política de senha completa (`login.md`, 5.2): 15 a 128 caracteres, sem
      regra de composição, Unicode com normalização NFC, lista de bloqueio
      (**contendo ao menos** `security/pentest/senhas_bloqueadas_minimas.txt`),
      senha contextual e padrões triviais rejeitados, erro `SENHA_FRACA` sem eco
      da senha
- [x] Verificação sempre executada contra um hash fictício quando o usuário não
      existe (anti-temporização) e regravação do hash quando os parâmetros mudam
- [x] Testes de integração do backend para cada regra e para os parâmetros do
      hash lidos da string PHC

**Especificação:** `login.md`, 5.2 e 5.3.
**Dependências:** AUTH01.
**Verifica:** `test_11_politica_de_senha.py`, `test_12_banco_e_hash.py`.

## AUTH03 — Sessão e endpoints de autenticação

- [x] Token de 256 bits (`secrets.token_urlsafe(32)`), guardado só como SHA-256;
      sessão nova a cada login, token imposto pelo cliente nunca aceito
- [x] Cookie `__Host-` com `Secure`, `HttpOnly`, `SameSite=Strict`, `Path=/`, sem
      `Domain` e sem `Max-Age` (em desenvolvimento, `COOKIE_SECURE=false` e nome
      sem prefixo, apenas com `AMBIENTE=desenvolvimento`)
- [x] Prazos de 30 min de inatividade e 8 h absolutos, até 5 sessões
      simultâneas, renovação limitada; **todos configuráveis por variável de
      ambiente** (a homologação usa valores curtos)
- [x] `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me` e
      `POST /api/auth/senha` (revoga as demais sessões), todos com `Cache-Control:
      no-store`
- [x] Resposta única `CREDENCIAIS_INVALIDAS` para qualquer falha (conta
      inexistente, senha errada, inativa **e bloqueada**), na ordem de
      verificações de `login.md`, 6.2
- [x] Bloqueio de 15 min após 5 falhas por conta e `429` com `Retry-After`
      após 30 falhas por IP, **ambos configuráveis**; nunca bloqueio permanente
- [x] IP real só de `X-Forwarded-For` vindo do proxy
      (`--forwarded-allow-ips` restrito)
- [x] Log de auditoria dos eventos de `login.md`, 12.1, sem senha, hash, token
      nem e-mail digitado

**Especificação:** `login.md`, seções 6 e 7.
**Dependências:** AUTH02.
**Verifica:** `test_04_autenticacao.py`, `test_05_sessao.py`.

## AUTH04 — Proteção global, CSRF e abuso

- [x] Dependência `usuario_atual` aplicada **no roteador-raiz**: rota nova nasce
      protegida; as exceções (`login`, `healthz`) são explícitas
- [x] CSRF: token sincronizado em `X-CSRF-Token`, comparação em tempo constante,
      verificação de `Origin`/`Referer` em métodos não seguros (inclusive no
      login), `403 CSRF_INVALIDO`
- [x] CORS com origens explícitas e credenciais, nunca `*`
- [x] Limite de análises por usuário (padrão 30 por minuto, `429
      LIMITE_ANALISES`, configurável)
- [x] `/docs`, `/redoc` e `/openapi.json` desativados com `AMBIENTE=producao`
- [x] Mídia (`/imagem`, `/mascara`) só com sessão
- [x] Teste de varredura que percorre as rotas e falha se alguma sair da lista
      de exceções sem exigir sessão

**Especificação:** `login.md`, seções 8 e 9.
**Dependências:** AUTH03.
**Verifica:** `test_06_csrf_cors.py`, `test_07_autorizacao.py`,
`test_08_injecao.py`, `test_09_upload.py`, `test_10_abuso.py`.

## AUTH05 — Gestão de contas por linha de comando

- [x] `criar-usuario`, `redefinir-senha`, `desativar-usuario`, `ativar-usuario`,
      `desbloquear-usuario` e `listar-usuarios`
- [x] Senha lida por `getpass` (sem eco, nunca por argumento nem variável de
      ambiente) e validada pela política de AUTH02
- [x] Desativar e redefinir revogam todas as sessões
- [x] **Sem usuário nem senha padrão** em nenhum ambiente; o seed de demonstração
      não cria credenciais; `listar-usuarios` nunca mostra o hash

**Especificação:** `login.md`, 5.4.
**Dependências:** AUTH02.

## AUTH06 — Frontend de autenticação

- [x] Rota pública `/login`; demais rotas exigem sessão, com redirecionamento
      preservando o destino
- [x] Contexto de autenticação carregado por `GET /api/auth/me` ao abrir o app,
      sem exibir conteúdo protegido enquanto carrega
- [x] `fetch` com credenciais (`same-origin` em produção, `include` em
      desenvolvimento) e `X-CSRF-Token` em métodos não seguros
- [x] `401 NAO_AUTENTICADO` limpa o estado e leva ao login com aviso de sessão
      expirada, sem repetir a requisição em laço
- [x] Nenhum token, senha ou `csrf_token` em `localStorage` ou `sessionStorage`
- [x] Formulário acessível (`autocomplete` correto, colagem permitida, erro único
      "E-mail ou senha inválidos."), troca de senha e botão de logout
- [x] `VITE_API_URL` relativo (`/api`) em produção; o módulo de mídia aceita
      caminho relativo na mesma origem

**Especificação:** `login.md`, seção 11; `../plan/frontend/telas_spec.md`.
**Dependências:** AUTH03, AUTH04.
**Verifica:** testes do frontend e a lista manual de `seguranca_testes.md`, seção 9.

## AUTH07 — Criação de contas pelo gerente

- [x] Especificar dois papéis, gerente único e troca inicial obrigatória
- [x] Migration 0010 com papel, CHECK e gerente único; flag em migration própria
- [x] GET/POST /api/usuarios só para gerente, CSRF, erros estáveis e auditoria
- [x] CLI criar-usuario --papel e definir-papel com revogação de sessões
- [x] Tela Contas, menu condicionado e guarda contra acesso direto de operador
- [x] Troca pendente global no middleware e encaminhamento no frontend
- [x] Testes API, CLI, migrations e frontend; validação completa e produção

**Especificação:** login.md, 4.3 e 5.4; api_spec.md, 3.2; telas_spec.md, 4.6.
**Dependências:** AUTH01 a AUTH06.
**Concluída em:** 2026-10-26, confirmada pelo usuário.

**Auditoria durável (2026-10-28):** os eventos da CLI são gravados na tabela
`auditoria_cli` (migração 0012), com o papel de execução limitado a inserir e
consultar.

**Pendências conhecidas:** a execução da suíte de segurança em homologação (SEG03),
que inclui os testes novos de gestão de contas. A tela Contas é coberta por testes
automatizados, mas não foi exercitada num navegador.

## HOST01 — Build e imagens de produção

- [x] Frontend como **build estático** (o servidor de desenvolvimento nunca vai a
      produção)
- [x] Imagens com usuário não-root, base mínima e **versão fixa** (nunca
      `latest`), sistema de arquivos somente leitura quando possível,
      `no-new-privileges`, sem capacidades extras e com limites de memória e CPU
- [x] Nenhum segredo dentro da imagem nem do repositório

**Especificação:** `login.md`, 10.1 e 10.6; `../rules/security_spec.md`, 10.1.
**Dependências:** AUTH06.

## HOST02 — Compose de produção e proxy

- [x] `docker-compose.prod.yml` separado, sem *bind mounts* de código
- [x] **Somente o proxy publica portas (80 e 443)**; `backend`, `frontend` e `db`
      sem `ports:`, em rede interna
- [x] Caddy com HTTPS automático, redirecionamento de HTTP, `/api` para o backend
      e o restante para o frontend estático (mesma origem)
- [x] Cabeçalhos do proxy (`login.md`, 10.2): HSTS sem `preload`, `nosniff`,
      `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, `Cache-Control`
      nas rotas de autenticação, `Server` e `X-Powered-By` removidos; CSP em
      modo de relatório (10.3)
- [x] Nenhum `privileged`, `network_mode: host` nem `docker.sock` em nenhum serviço
- [x] Banco: `pg_hba.conf` só `scram-sha-256` e só a rede interna, senha única e
      forte por ambiente, volume nomeado
- [x] Backup periódico (`pg_dump`) fora do servidor web, restrito e, se sair da
      máquina, cifrado

**Especificação:** `login.md`, seções 10.1 a 10.6.
**Dependências:** HOST01; decisão de provedor e domínio (`completed/current_task_externo.md`,
EXT04).
**Verifica:** `test_01_exposicao.py`, `test_02_transporte.py`,
`test_03_vazamento_info.py`, `test_12_banco_e_hash.py` e o nmap.

**Estado do backup (2026-10-28):** `scripts/backup-banco.sh`,
`scripts/restaurar-banco.sh` e `scripts/testar-restauracao.sh` estão prontos e
commitados, com cifra por chave pública própria e teste de restauração real
(8 tabelas, 9 linhas, 3 imagens conferidas por SHA-256). Item concluído por
decisão do usuário em 2026-10-28. Ficam para a publicação: o agendamento
periódico e a restauração testada contra o Supabase real; ver `../../deploy/backup-restauracao.md`.

## HOST03 — Ambientes e servidor

- [ ] **Homologação descartável** com a mesma configuração do definitivo e
      credenciais de teste próprias (nunca de pessoas reais)
- [ ] Na homologação, prazos de sessão curtos e limites configurados para as três
      passadas da suíte (`security/README.md`)
- [ ] Somente com servidor próprio: firewall do **provedor** com negação por
      padrão (entrada só 80/443 e SSH por chave, restrito à origem do
      administrador); o do host não substitui esse, porque o Docker o contorna
- [ ] Somente com servidor próprio: atualizações de segurança do sistema
      operacional ativas; SSH sem senha
- [ ] Contas de teste criadas por `criar-usuario` (AUTH05)

**Especificação:** `login.md`, 10.5 (regra 8) e 10.7;
`../validation/seguranca_testes.md`, seção 7.
**Dependências:** HOST02, AUTH05.

## SEG01 — Rodada 0: linha de base (cega)

- [ ] Executar `executar_cego.sh` nos modos `codigo`, `pentest` (local), `passivo`
      e `rede` contra o ambiente **local** (sem ataque ativo)
- [ ] Entregar os relatórios cifrados ao revisor
- [ ] Revisor abre, classifica por severidade e separa achado real, falso positivo
      e problema de ferramenta
- [ ] Registrar as flags de ferramenta que precisaram de ajuste e fixar os
      digests das imagens

**Especificação:** `../validation/seguranca_testes.md`, seções 5, 8 e 11.
**Dependências:** nenhuma (pode ser feita **agora**, antes do login).
**Nota:** o resultado esperado antes do login é a lista de pendências que as
demais tasks resolvem.

## SEG02 — Correção dos achados

- [ ] Achados de código, dependência, imagem e configuração corrigidos, cada um
      descrito como violação da especificação (sem repassar saída de teste)
- [ ] Nova execução cega após cada rodada de correção
- [ ] **Crítico e alto: zero.** Médios triados por escrito (corrigir ou aceitar
      com justificativa, responsável e prazo)

**Dependências:** SEG01 e as tasks de implementação relacionadas.

## SEG03 — Suíte completa na homologação

- [ ] Passada 1 (funcional), passada 2 (limites) e passada 3 (expiração)
      verdes, com as 12 áreas da suíte
- [ ] ZAP *API scan* e *full*, Nuclei ativo e sqlmap no login, **somente na
      homologação**
- [ ] Teste do banco com `SEC_DB_DSN_APP` e `SEC_DB_DSN_ADMIN`, executor na rede
      interna
- [ ] Checklist manual de `seguranca_testes.md`, seção 9, com capturas
- [ ] Relatório arquivado (data, commit, digests, exceções aceitas e veredito)

**Dependências:** AUTH01 a AUTH06, HOST03, SEG02.

## SEG04 — Ataque exploratório do revisor

- [ ] Rodada de ataque manual na homologação, conforme as regras de engajamento
      (`seguranca_testes.md`, seção 12): lógica, condições de corrida, colisão de
      contas por Unicode, contorno de CSRF e `Origin`, entropia dos tokens,
      cache, bundle do frontend, upload e proxy
- [ ] Achados com identificador, severidade, passos de reprodução e correção
      recomendada
- [ ] Reteste de cada correção até zero crítico e alto

**Dependências:** SEG03.

## SEG05 — Publicação e verificação final

- [ ] Teste de TLS contra o **definitivo**: TLS 1.2 ou superior, certificado
      válido, HSTS; a varredura de portas (somente 80 e 443) vale para o Compose
      local, porque a Vercel e o Supabase não são infraestrutura do projeto
- [ ] ZAP *baseline* (passivo) contra o definitivo
- [ ] Banco, backend e demais serviços **inacessíveis** de fora no Compose local
      (conexão direta falha); no Supabase, o banco só aceita conexão com TLS e o
      papel dedicado, e os papéis `anon` e `authenticated` não alcançam as tabelas
- [ ] Relatório final aprovado e arquivado; qualquer exceção aceita registrada
- [ ] README com a seção de hospedagem e o status atualizados
- [ ] Rotina de verificação semanal ativa (dependências, imagens e ZAP
      *baseline*) conforme `seguranca_testes.md`, seção 10

**Dependências:** SEG04, HOST02.

---

# 4. Ordem de execução

```text
AUTH00 ─▶ AUTH01 ─▶ AUTH02 ─┬─▶ AUTH03 ─▶ AUTH04 ─▶ AUTH06 ─▶ HOST01 ─▶ HOST02 ─▶ HOST03
                            └─▶ AUTH05 ───────────────────────────────────────────┘
SEG01 (agora) ─▶ SEG02 ─▶ SEG03 ─▶ SEG04 ─▶ SEG05
```

- **SEG01 pode rodar já**, em paralelo com tudo: não depende do login.
- AUTH05 (CLI) corre em paralelo a AUTH03 e AUTH04.
- HOST03 exige AUTH05 (contas de teste).
- SEG03 só começa com a homologação no ar.

---

# 5. Critério de conclusão

O protótipo está **online**, e todas as condições abaixo valem ao mesmo tempo:

1. No Compose local, só as portas 80 e 443 respondem e o banco e o backend são
   inalcançáveis de fora. No ambiente publicado, o navegador só fala HTTPS com a
   mesma origem e a segurança do banco fica a cargo do Supabase (TLS obrigatório,
   papel dedicado de menor privilégio, RLS e nenhuma chave Supabase no navegador).
2. Toda rota de dados exige sessão, e o login resiste à suíte de invasão.
3. As três passadas da suíte, o checklist manual e o ataque exploratório fecham
   com **zero achado crítico ou alto**.
4. O relatório final está arquivado e as exceções aceitas estão registradas.

---

# FIM DA TASK — AUTENTICAÇÃO E HOSPEDAGEM
