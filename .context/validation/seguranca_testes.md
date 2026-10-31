# TESTES DE SEGURANÇA E INVASÃO — Projeto Integrador

**Versão:** 1.0
**Status:** ATIVO
**Escopo:** especificação dos testes de invasão e das varreduras de segurança que precedem toda publicação

---

# 1. Objetivo e regra

Provar, com evidência repetível, que o sistema publicado **não tem nada aberto**
e que a autenticação resiste aos ataques mais comuns. A origem dos requisitos é
`../plan/foundation/login.md` (em especial as seções 1.1, 10.5 a 10.7 e 14).

> **Nenhuma publicação sem a suíte verde e o relatório arquivado.**
> **Controle sem teste é controle inexistente.**

A suíte é executável (`security/` na raiz do repositório) e foi escrita **antes**
da implementação do login: ela serve de critério de aceite. Contra o código
atual ela **falha de propósito** (rotas abertas sem sessão, `/docs` público,
sem HTTPS). Cada item de `login.md`, seção 15, implementado deve fazer os
testes correspondentes passarem.

---

# 2. Autorização e segurança dos próprios testes

Testes de invasão só podem ser executados contra sistemas **de nossa
propriedade**, com autorização do responsável.

| Regra | Detalhe |
|---|---|
| Alvos permitidos | O ambiente local, a **homologação** e o ambiente definitivo do TrapSight. **Nunca** terceiros, nem o servidor do provedor, nem sistemas da empresa parceira |
| Ataque ativo | **Somente em homologação**: cópia descartável, com dados fictícios, que pode ser destruída. Varredura ativa (ZAP *full/API*, sqlmap, testes de força bruta) **nunca** roda contra o definitivo |
| Contra o definitivo publicado | Apenas TLS e ZAP *baseline* (passivo); a varredura de portas vale para o Compose local, pois Vercel e Supabase controlam suas redes (decisão de 2026-10-26) |
| Credenciais de teste | Contas **dedicadas e descartáveis**, criadas por `criar-usuario` na homologação (seção 7). **Nunca** a conta de uma pessoa real. Valores só em variáveis de ambiente, nunca no repositório, nunca em relatório |
| Efeitos colaterais | Os testes criam armadilhas e análises fictícias, bloqueiam contas de teste e consomem limites de taxa. Por isso só rodam na homologação |
| Relatórios | Podem conter detalhes da superfície e evidências; ficam em `security/reports/` (ignorado pelo Git) e **nunca** são publicados |

---

# 3. Estratégia em camadas

Seguindo a prática de mercado: cada camada pega uma classe de falha que a
outra não pega, e todas rodam antes de publicar.

| Camada | O que cobre | Ferramenta | Quando |
|---|---|---|---|
| **1. Segredos** | Credencial no código e no histórico do Git | **gitleaks**, **Trivy** (scanner de segredos) | Todo commit relevante e antes de publicar |
| **2. Dependências (SCA)** | Vulnerabilidades conhecidas em pacotes | **pip-audit**, **npm audit**, **Trivy** (`fs`) | Antes de publicar e semanalmente |
| **3. Código (SAST)** | Padrões inseguros no código | **Semgrep** (regras OWASP Top 10, Python, TypeScript), **Bandit** (Python) | Antes de publicar |
| **4. Contêineres e configuração (IaC)** | Imagens vulneráveis, Dockerfile e Compose inseguros, exposição | **Trivy** (`image`, `config`), **hadolint** | Antes de publicar |
| **5. Exposição de rede** | Portas abertas, banco acessível, serviços internos | **nmap** (`-p-`), testes de porta da suíte | Antes de publicar, contra o Compose local; as redes publicadas são dos provedores (decisão de 2026-10-26) |
| **6. Transporte (TLS)** | Versões, cifras, certificado, HSTS | **testssl.sh**, testes de TLS da suíte | Antes de publicar, contra o definitivo |
| **7. Caixa-preta da aplicação** | Autenticação, sessão, CSRF, autorização, injeção, upload, vazamento de informação | **Suíte `security/pentest` (pytest + httpx)** | Antes de publicar, na homologação |
| **8. DAST** | Varredura de vulnerabilidades web por ferramenta | **OWASP ZAP** (*baseline*, *API scan*, *full*), **Nuclei** | *Baseline* no definitivo; *API* e *full* só na homologação |
| **9. Injeção dirigida** | Confirmação de injeção de SQL nos pontos de entrada | **sqlmap** (nível 2, risco 1) | Homologação, quando houver mudança em entrada de dados |
| **10. Manual** | O que não se automatiza bem (seção 9) | Checklist com navegador | Antes da primeira publicação e a cada mudança de autenticação |

---

# 4. Mapeamento com o OWASP WSTG

A suíte segue o catálogo do **OWASP Web Security Testing Guide v4.2**. A coluna
"Cobertura" diz onde cada teste é exercitado.

| WSTG | Teste do guia | Cobertura |
|---|---|---|
| CONF-01 | Infraestrutura de rede | `test_01_exposicao`, nmap, Trivy `config` |
| CONF-02 | Plataforma da aplicação | `test_03_vazamento_info`, Nuclei |
| CONF-04 | Arquivos de backup e não referenciados | `test_03_vazamento_info`, Nuclei `exposures` |
| CONF-05 | Interfaces de administração | `test_03_vazamento_info`, `test_01_exposicao` |
| CONF-06 | Métodos HTTP | `test_03_vazamento_info`, `test_07_autorizacao` |
| CONF-07 | HSTS | `test_02_transporte`, testssl.sh |
| IDNT-04 | Enumeração de contas | `test_04_autenticacao` |
| ATHN-01 | Credenciais por canal cifrado | `test_02_transporte` |
| ATHN-02 | Credenciais padrão | `test_04_autenticacao`, Nuclei `default-logins` |
| ATHN-03 | Mecanismo de bloqueio fraco | `test_04_autenticacao` |
| ATHN-04 | Contorno da autenticação | `test_07_autorizacao` |
| ATHN-06 | Cache do navegador | `test_05_sessao` |
| ATHN-07 | Política de senha fraca | testes de integração do backend (`login.md`, seção 14) |
| ATHN-09 | Troca e recuperação de senha | `test_05_sessao` (troca), `login.md` 5.4 |
| ATHZ-01 | Travessia de diretório | `test_07_autorizacao`, `test_09_upload` |
| ATHZ-02 | Contorno da autorização | `test_07_autorizacao` |
| SESS-01 | Esquema de gerência de sessão | `test_05_sessao` |
| SESS-02 | Atributos do cookie | `test_05_sessao` |
| SESS-03 | Fixação de sessão | `test_05_sessao` |
| SESS-05 | CSRF | `test_06_csrf_cors` |
| SESS-06 | Logout | `test_05_sessao` |
| SESS-07 | Expiração da sessão | `test_05_sessao` |
| SESS-09 | Sequestro de sessão | `test_05_sessao`, `test_02_transporte` |
| INPV-01/02 | XSS refletido e armazenado | `test_08_injecao`, ZAP, manual |
| INPV-03/04 | Troca de verbo e poluição de parâmetros | `test_07_autorizacao`, `test_08_injecao` |
| INPV-05 | Injeção de SQL (inclui PostgreSQL e ORM) | `test_04_autenticacao`, `test_08_injecao`, sqlmap |
| INPV-17 | Injeção de cabeçalho `Host` | `test_03_vazamento_info` |
| ERRH-01/02 | Tratamento de erro e pilha | `test_03_vazamento_info` |
| CRYP-01 | TLS fraco | `test_02_transporte`, testssl.sh |
| CRYP-03 | Informação em canal não cifrado | `test_01_exposicao` (redirecionamento), `test_02_transporte` |
| BUSL-05 | Limite de uso de uma função | `test_10_abuso`, `test_04_autenticacao` |
| BUSL-08/09 | Upload de tipos inesperados e de arquivos maliciosos | `test_09_upload` |
| CLNT-07 | CORS | `test_06_csrf_cors` |
| CLNT-09 | *Clickjacking* | `test_02_transporte` (cabeçalhos) |
| CLNT-12 | Armazenamento do navegador | Manual (seção 9) |

Para o padrão de verificação, os requisitos de autenticação, sessão e
autorização seguem o **OWASP ASVS 5.0** (capítulos V6, V7 e V8), nível de
referência **L2**, adequado a aplicações em geral.

---

# 5. Ferramentas do mercado e comandos

Tudo roda em **contêiner**, sem instalar nada na máquina. O orquestrador é
`security/scans/run_scans.sh` (seção 6 de `security/README.md`). As versões das
imagens devem ser **fixadas pelo digest** no primeiro uso e registradas no
relatório; uma varredura não reproduzível não serve de evidência.

| Ferramenta | Imagem | Uso | Critério de aprovação |
|---|---|---|---|
| gitleaks | `ghcr.io/gitleaks/gitleaks` | `detect --source /repo --log-opts="--all"` (histórico completo) | **Zero** segredos |
| Trivy `fs` e `image` | `aquasec/trivy` | `fs --scanners vuln,secret,misconfig`; `image --severity HIGH,CRITICAL` | Zero crítico e alto sem correção disponível ignorada com justificativa |
| Trivy `config` | `aquasec/trivy` | Dockerfiles do repositório (o Compose não é analisado pelo Trivy: revisar à mão com a seção 10.5 de `login.md`) | Zero crítico e alto |
| hadolint | `hadolint/hadolint` | Dockerfiles | Sem erro |
| pip-audit | `python:3.12-slim` + `pip-audit` | `-r backend/requirements.txt` | Zero vulnerabilidade com correção disponível |
| npm audit | `node:24` | `npm audit --omit=dev` em `frontend/` | Zero alto e crítico |
| Semgrep | `semgrep/semgrep` | `--config p/owasp-top-ten --config p/python --config p/typescript` | Zero achado alto; médio triado |
| Bandit | `python:3.12-slim` + `bandit` | `-r backend/src -ll` | Zero alto |
| nmap | `instrumentisto/nmap` | `-p- -sV -Pn --open` no host do Compose local | **Somente 80 e 443** (mais SSH restrito, se houver); não varrer a rede do provedor publicado (decisão de 2026-10-26) |
| testssl.sh | `drwetter/testssl.sh` | `--severity MEDIUM --quiet` | Sem TLS 1.0/1.1, sem cifras fracas, certificado válido, HSTS presente |
| OWASP ZAP *baseline* | `ghcr.io/zaproxy/zaproxy:stable` | `zap-baseline.py -t URL -r relatorio.html -J relatorio.json` (passivo) | Nenhum alerta alto; médios triados |
| OWASP ZAP *API scan* | idem | `zap-api-scan.py -t openapi.json -f openapi -n contexto -U usuario` (ativo, só homologação, autenticado) | Nenhum alerta alto |
| OWASP ZAP *full* | idem | `zap-full-scan.py -t URL` (ativo, só homologação) | Nenhum alerta alto |
| Nuclei | `projectdiscovery/nuclei` | `-tags exposure,misconfig,default-login,tech -severity low,medium,high,critical` | Zero alto e crítico |
| sqlmap | `paoloo/sqlmap` ou imagem equivalente | `--batch --level=2 --risk=1` nos pontos de entrada | Nenhuma injeção confirmada |

Observações verificadas na documentação:

- O ZAP *baseline* é **passivo**: roda o *spider* por alguns minutos e analisa
  as respostas, sem atacar; foi desenhado para CI e pode rodar contra produção.
- O ZAP *API scan* importa a definição OpenAPI e executa uma varredura **ativa**
  ajustada para APIs; a autenticação é passada por arquivo de contexto
  (`-n`) e usuário (`-U`). Como `/openapi.json` é fechado em produção, o
  arquivo é **gerado offline** a partir do código (`app.openapi()`) e entregue ao
  contêiner.
- Códigos de saída do ZAP: `0` sucesso, `1` falha, `2` aviso sem falha, `3` outro
  erro. A suíte trata `1` como reprovação.
- O Trivy analisa Dockerfile e Containerfile; **não** analisa o `docker-compose.yml`.
  A conferência do Compose é manual (checklist da seção 9) e reforçada pela
  varredura externa de portas, que é a prova definitiva.

---

# 6. Suíte caixa-preta (`security/pentest`)

Arquivos, um por área, todos parametrizados por variáveis de ambiente
(seção 7):

| Arquivo | Área | Exige login | Destrutivo |
|---|---|---|---|
| `test_01_exposicao.py` | Portas abertas, banco inalcançável, HTTP→HTTPS | Não | Não |
| `test_02_transporte.py` | HTTPS, certificado, TLS, HSTS, cabeçalhos | Não | Não |
| `test_03_vazamento_info.py` | Arquivos sensíveis, `/docs`, pilhas de erro, métodos, `Host` | Não | Não |
| `test_04_autenticacao.py` | Anti-enumeração, tempo, credenciais padrão, injeção, bloqueio de conta | Parcial | **Sim** (bloqueia a conta de teste de bloqueio) |
| `test_05_sessao.py` | Cookie, entropia, fixação, logout, limite de sessões, expiração | Sim | Cria sessões |
| `test_06_csrf_cors.py` | CSRF, `Origin`, CORS | Sim | Não |
| `test_07_autorizacao.py` | Toda rota exige sessão, normalização de caminho, verbos; gestão de contas só pelo gerente, escalada de papel e portão da troca obrigatória | Parcial (operador e gerente) | Cria contas fictícias |
| `test_08_injecao.py` | SQL, XSS, SSTI, parâmetros malformados | Sim | Cria registros fictícios |
| `test_09_upload.py` | Arquivos maliciosos, bomba de descompressão, travessia | Sim | Cria registros fictícios |
| `test_11_politica_de_senha.py` | Política de senha: 14 rejeitadas, 15 aceitas, sem regra de composição, Unicode/NFC, teto de 128, lista mínima, senha contextual, padrões triviais, sem eco da senha | Sim (conta de troca) | **Sim** (troca a senha da conta de teste e a restaura) |
| `test_12_banco_e_hash.py` | Banco: papel sem privilégios, sem alterar esquema, credenciais padrão recusadas, Argon2id com parâmetros mínimos, token só como hash, sem coluna de segredo em claro, `pg_hba` sem `trust`, gerente único e papel válido garantidos pelo banco, papel rebaixado vale na requisição seguinte | Sim (e acesso ao banco pela rede interna) | Não |
| `test_10_abuso.py` | Limite de análises, limite de criação de contas, corpos gigantes e, **por último**, limite de tentativas por IP | Sim | **Sim** (esgota limites; a cota de criação do gerente e o IP do executor ficam bloqueados) |

**Os testes afirmam o estado final desejado**, não o atual. Antes da
implementação do login, os testes que não exigem sessão (exposição, transporte,
vazamento, autorização) **já executam e falham**, produzindo a lista de
pendências; os que exigem login são **ignorados com motivo explícito**
(credenciais ausentes) e não aprovados em silêncio. Um teste ignorado **não
conta como aprovado** no relatório.

---

# 7. Variáveis de ambiente da suíte

Nenhum valor aqui é versionado.

| Variável | Obrigatória | Função |
|---|---|---|
| `TARGET_URL` | Sim | Origem do sistema (`https://homologacao.exemplo.com` ou `http://backend:8000` no baseline local) |
| `API_PREFIX` | Não (`/api`) | Prefixo da API |
| `TARGET_HOST` | Não | Host do Compose local para varredura de portas; a suíte usa o host de `TARGET_URL` por padrão, portanto não use o teste de portas no publicado, cuja rede é do provedor (decisão de 2026-10-26) |
| `EXPECTED_OPEN_PORTS` | Não (`80,443`) | Portas que **podem** estar abertas |
| `SEC_USER_EMAIL`, `SEC_USER_PASSWORD` | Para testes autenticados | Conta de teste da homologação (precisa ser **operador**) |
| `SEC_MANAGER_EMAIL`, `SEC_MANAGER_PASSWORD` | Para a gestão de contas | Conta do **gerente** (`criar-usuario --papel gerente`); cria as contas fictícias dos testes |
| `SEC_LOCKOUT_EMAIL`, `SEC_LOCKOUT_PASSWORD` | Para o teste de bloqueio | Conta **separada**, que fica bloqueada (usar `desbloquear-usuario` depois) |
| `SEC_CHANGEPWD_EMAIL`, `SEC_CHANGEPWD_PASSWORD`, `SEC_CHANGEPWD_NEW` | Para a troca de senha e a política de senha | Conta separada |
| `SEC_DB_DSN_APP` | Para `test_12` | DSN do usuário **da aplicação** (só em variável de ambiente; o executor precisa estar na rede interna do Compose) |
| `SEC_DB_DSN_ADMIN` | Opcional (`pg_hba`) | DSN administrativo, só para ler as regras de acesso |
| `SEC_IDLE_TIMEOUT_SECONDS` | Para expiração | Valor curto de inatividade configurado **na homologação** (ex.: 5) |
| `SEC_ABSOLUTE_TIMEOUT_SECONDS` | Para expiração | Valor curto de duração absoluta (ex.: 15) |
| `SEC_RUN_RATE_LIMIT` | Não (`0`) | `1` liga os testes que esgotam limites (login por IP, análises, criação de contas) |
| `PASSADA`, `PYTEST_ARGS` | Não | Nomeiam o relatório e selecionam testes em cada passada (abaixo) |

**Três passadas na homologação** (comandos em `security/README.md`): (1) funcional, com o limite de tentativas por IP **elevado**; (2) limites, com os valores padrão e `SEC_RUN_RATE_LIMIT=1`; (3) expiração, com prazos curtos. Sem isso o limite de IP é esgotado pelos próprios testes e geraria falsos `429`.

**Requisito para a implementação:** o limite de tentativas por IP e os prazos de sessão (7.3 de `login.md`) e
os limites (6.3 e 9.4) devem ser **configuráveis por variável de ambiente**, para
a homologação poder usar valores curtos sem alterar o código.

---

## 6.1 Calibração da própria suíte (evidência de 2026-10-16)

Uma suíte de segurança só vale se detecta falhas de verdade. Antes de ser
entregue, foi calibrada de três formas:

| Verificação | Resultado |
|---|---|
| **Contra o sistema atual** (sem login) | 58 falham (rotas abertas sem sessão, `/docs` público, `/auth/login` inexistente, sem HTTPS, porta do backend acessível), 97 passam, 104 são ignoradas por falta de credencial |
| **Contra um servidor de referência** que implementa o contrato de `login.md` | Todos os testes passam, **exceto os 9 da camada de proxy/TLS** (HTTPS, HSTS, CSP, cabeçalhos, `Server`), que só existem com o Caddy. Passada de limites: 2/2. Passada de expiração: 2/2 |
| **Teste de mutação**: 23 defeitos deliberados no servidor de referência e no banco de calibração | **23/23 detectados**. Autenticação e sessão: código de erro diferente do contrato (`NAO_AUTENTICADO`), CSRF desligado, cookie sem `HttpOnly`/`SameSite`, mensagem que revela a conta, logout sem revogar, fixação de sessão, mídia sem autenticação, erro 500 com SQL, ausência de bloqueio, token fraco, CORS `*` com credenciais. Política de senha: mínimo de 8, regra de composição, sem normalização Unicode, sem lista de bloqueio, erro que devolve a senha, troca sem confirmar a atual. Banco: papel superusuário, hash Argon2id fraco, token em claro, credencial padrão (`admin/admin`), `pg_hba` com `trust`, `pg_hba` aberto a todos |

O servidor de referência e o banco de calibração foram descartáveis e não
fazem parte do repositório. A calibração revelou quatro defeitos da própria
suíte, já corrigidos: os testes de enumeração e de tempo bloqueavam a conta de
teste principal por errar a senha demais; o teste de limite por IP esgotava o
IP no meio da execução; uma variante de token com espaço no fim era rejeitada
pelo cliente HTTP antes de sair; e o teste de "erro não devolve a senha" era
vazio (a senha escolhida era aceita, então nunca havia erro para conferir). **Limite honesto:** os testes autenticados só foram exercitados contra
esse servidor de referência, não contra a implementação real, que ainda não
existe. Quando ela existir, cada divergência deve ser analisada caso a caso
(defeito da implementação ou da suíte) antes de qualquer ajuste de teste.

# 8. Critérios de aprovação e relatório

| Severidade | Regra |
|---|---|
| **Crítica e alta** | Bloqueiam a publicação. Sem exceção |
| **Média** | Precisa de triagem: corrigir, ou aceitar por escrito com justificativa, responsável e prazo |
| **Baixa e informativa** | Registrar; corrigir quando barato |
| **Teste ignorado** | Conta como **não verificado**. Para publicar, todo teste obrigatório precisa ter rodado |
| **Falso positivo** | Só vale com explicação técnica registrada e o item ajustado na lista de exceções |

Cada execução gera `security/reports/AAAA-MM-DD_<commit>/` com:

- `RESUMO.md`: tabela por camada (aprovado, reprovado, ignorado), achados por
  severidade, exceções aceitas, ambiente testado, versão do código, **digests das
  imagens** das ferramentas e o veredito final (**APROVADO** ou **REPROVADO**);
- a saída bruta de cada ferramenta (HTML, JSON ou texto);
- o resultado do `pytest` (`junit.xml`).

---

# 9. Verificação manual (checklist com navegador)

O que não se automatiza bem. Marcar e anexar capturas ao relatório antes da
primeira publicação e a cada mudança de autenticação.

- [ ] Em **DevTools → Application → Cookies**: o cookie de sessão tem `Secure`,
      `HttpOnly`, `SameSite=Strict`, prefixo `__Host-` e é de sessão (sem data de expiração).
- [ ] Em **Application → Local Storage e Session Storage**: **nenhum** token,
      senha ou `csrf_token`.
- [ ] No console, `document.cookie` **não** mostra o cookie de sessão.
- [ ] Logout em uma aba invalida a outra aba na próxima ação (`401` e volta ao login).
- [ ] Botão "voltar" após o logout **não** exibe dados protegidos (cache).
- [ ] Digitar `<img src=x onerror=alert(1)>` em identificador, localização e
      modelo: aparece como **texto**, sem executar, na lista, no detalhe e no gráfico.
- [ ] Abrir o site por `http://`: redireciona para `https://` e o certificado é válido.
- [ ] A página de login não diferencia "e-mail não existe" de "senha errada".
- [ ] Colar a senha no campo funciona (gerenciador de senha).
- [ ] Revisão do `docker-compose.prod.yml`: **nenhum** `ports:` além do proxy;
      nenhum `privileged`, `network_mode: host`, `docker.sock`; nenhuma senha em claro.
- [ ] No Compose local, em um terminal **fora do servidor**:
      `Test-NetConnection <host> -Port 5432` (ou `nc -vz`) falha; só 80 e
      443 respondem. No publicado, a rede é do provedor e verificam-se TLS e
      controles do Supabase (decisão de 2026-10-26).
- [ ] Os logs do servidor registram falhas de login e **não** contêm senhas,
      hashes nem tokens.

---

# 10. Cadência

| Quando | O quê |
|---|---|
| A cada commit relevante | Camada 1 (segredos) |
| A cada **publicação** | Camadas 1 a 8 completas e o checklist manual, se a autenticação mudou |
| Semanal, com o sistema no ar | Camadas 2 e 4 (dependências e imagens), mais o ZAP *baseline* contra o definitivo |
| Após mudança de infraestrutura | Camadas 5 e 6 |
| A cada mudança em entrada de dados ou upload | Camada 9 (sqlmap) e `test_08`, `test_09` |

---

# 11. Execução cega (separação de funções)

Quem **implementa** o sistema **só executa** a suíte quando a verificação
precisa ser independente. Quem **revisa** é o único que lê os resultados. Isso
evita ajustar o sistema à resposta do teste.

> **Papéis atuais (2026-10-17).** A implementação de autenticação e hospedagem
> foi feita pelo Claude, que por isso rodou a suíte em modo direto, contra o
> ambiente local de produção, para corrigir o sistema (nunca os testes). A
> independência vem agora da **rodada do Codex** (seção 12): ele ataca o sistema
> implantado, sem acesso ao código-fonte da correção, e entrega achados com
> passos de reprodução. A execução cega continua válida para quem implementar
> alterações depois de uma rodada de ataque.

| Papel | Pode | Não pode |
|---|---|---|
| **Quem implementa** | Executar `security/scans/executar_cego.sh`; corrigir o ambiente quando uma etapa "não pôde ser executada"; implementar correções descritas como **violações da especificação** | Ler o relatório, procurar ou usar a chave privada, alterar testes ou scripts para melhorar o resultado, usar logs dos contêineres alvo para descobrir resultados |
| **Revisor / dono** | Abrir o relatório (`abrir_relatorio.sh`), classificar achados, decidir correções, atacar o sistema (seção 12) | Passar à implementação a saída bruta dos testes |

**Como funciona.** `executar_cego.sh` roda os modos pedidos em modo silencioso,
**cifra** o relatório inteiro (CMS, AES-256 com RSA-4096) para o certificado
público `security/cifra/certificado.pem` e apaga o texto claro. Na tela só
aparece: a execução ocorreu, o nome e o SHA-256 do arquivo cifrado e as etapas
que **não puderam ser executadas por problema de ambiente** (Docker ausente,
variável faltando), porque isso quem implementa precisa corrigir. A chave
privada fica **fora do repositório** (`~/.trapsight-seguranca/`).

**Como os achados voltam à implementação.** O revisor escreve a correção como
requisito, citando a especificação (ex.: "toda rota de dados exige sessão,
`login.md` 9.2"), sem repassar saída de teste. Depois da correção, o executor
cego roda de novo.

**Limites honestos.** Isto é um controle de **processo**, não uma barreira
técnica: o implementador roda no mesmo computador e pode ler o código dos
testes (o que é proposital, a suíte é o critério de aceite). Quem quiser mais
isolamento pode mover a chave privada para outra máquina ou mídia. Os logs dos
contêineres alvo registram as requisições e podem insinuar resultados; a regra
é não usá-los. O relatório cifrado não tem valor se a chave privada vazar:
protegê-la como qualquer segredo (seção 3 de `security_spec.md`).

# 12. Ataque exploratório (rodada do revisor)

Além da suíte automática, o **revisor tenta invadir o sistema** depois que o
login estiver implementado e houver homologação. A suíte prova o que foi
previsto; o ataque exploratório procura o que ninguém previu.

**Autorização.** Concedida pelo dono do projeto em 2026-10-16 ("você vai tentar
invadir depois nosso sistema"), **somente** contra o ambiente de homologação ou
local descartável do TrapSight.

**Regras de engajamento:**

| Regra | Detalhe |
|---|---|
| Alvo | Homologação (cópia descartável, dados fictícios) ou local. Nunca o definitivo com dados reais, nunca terceiros, nunca a infraestrutura do provedor |
| Credenciais | Contas de teste descartáveis, passadas por variável de ambiente da sessão (nunca coladas no chat) |
| Sem dano irreversível | Sem negação de serviço real, sem destruir dados fora do ambiente descartável, sem extrair credenciais reais |
| Evidência | Cada achado tem identificador, severidade, passos para reproduzir, evidência e correção recomendada |
| Divulgação | Achados vão ao dono do projeto; à implementação só como requisito (seção 11) |

**O que se explora (além do automatizado):** falhas de lógica e encadeamento de
vulnerabilidades; condições de corrida (troca de refil simultânea, contador de
bloqueio, limite de sessões); colisão de contas por normalização Unicode
(e-mail em caixa alta ou com caracteres de largura total); contorno de CSRF e
de `Origin`; amostragem estatística da entropia dos tokens; cabeçalhos e
cache; análise do bundle do frontend (segredos, rotas, mapas de código);
manipulação de parâmetros e de cabeçalhos; analisadores de upload; sequestro e
reuso de sessão; configuração do proxy. O roteiro segue o WSTG (seção 4).

**Quando:** uma vez antes da primeira publicação e depois de qualquer mudança
relevante em autenticação, sessão, proxy ou entrada de dados.

**Limite honesto:** é um teste feito por um revisor com as ferramentas desta
sessão, não substitui um teste de intrusão profissional independente. Se
passarem a existir dados reais ou sensíveis da empresa parceira em volume, a
recomendação é contratar essa auditoria.

# 13. Referências

- OWASP, [Web Security Testing Guide v4.2](https://wstg.owasp.org/v4.2/4-Web_Application_Security_Testing/): catálogo de testes e identificadores.
- OWASP, [Application Security Verification Standard](https://owasp.org/www-project-application-security-verification-standard/): requisitos de verificação (V6 autenticação, V7 sessão, V8 autorização).
- ZAP, [Baseline Scan](https://www.zaproxy.org/docs/docker/baseline-scan/), [API Scan](https://www.zaproxy.org/docs/docker/api-scan/) e [Docker](https://www.zaproxy.org/docs/docker/).
- Trivy, [cobertura de Docker](https://trivy.dev/docs/dev/coverage/iac/docker/).
- Projeto Nuclei, [documentação](https://nuclei.projectdiscovery.io/).

**Não verificado em fonte primária (conferir na primeira execução):** os
nomes exatos e as versões das imagens do Nuclei, do testssl.sh e do sqlmap, e
as opções de linha de comando de cada uma. O script registra o digest de cada
imagem usada e falha de forma explícita se uma delas não puder ser baixada.

---

# FIM DOS TESTES DE SEGURANÇA E INVASÃO
