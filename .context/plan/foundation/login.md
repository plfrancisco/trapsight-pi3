# LOGIN — Projeto Integrador

**Versão:** 1.1
**Status:** APROVADO (2026-10-16)
**Escopo:** autenticação, sessão, proteção de acesso e **exposição zero** de serviços internos na hospedagem pública do protótipo

---

# 1. Objetivo

Definir como o TrapSight autentica usuários quando o protótipo estiver
**online e acessível pela internet**. O alvo é o conjunto de práticas mais
usadas e recomendadas pela indústria (OWASP, NIST), com esforço compatível com
um protótipo: **seguro o bastante para exposição pública, sem pretender ser
impenetrável**.

Este documento **substitui** a decisão de risco aceito registrada em
`../../rules/security_spec.md`, seção 4, que exigia autenticação como
pré-requisito de qualquer implantação além da demonstração local. A lista de
documentos afetados está na seção 13.

## 1.1 Princípios inegociáveis

> **1. Nada fica aberto.** Nenhum serviço interno é alcançável pela internet:
> **nem o banco de dados, nem o backend, nem o servidor de desenvolvimento do
> frontend, nem o diretório de uploads, nem o socket do Docker.** A única
> superfície pública do sistema são as portas **80 e 443** do proxy reverso, e
> toda rota de dados exige sessão. As regras estão na seção 10.5.
>
> **2. Nada vai ao ar sem passar nos testes de invasão.** Toda publicação
> exige a suíte de segurança verde, com evidência arquivada. A suíte está
> especificada em `../../validation/seguranca_testes.md` e implementada em
> `security/` na raiz do repositório.
>
> **3. Ausência de prova é falha.** Um controle que não tem teste que o
> exercite é tratado como inexistente.

---

# 2. Contexto e premissas

| Premissa | Consequência |
|---|---|
| O protótipo fica online e acessível, para banca, empresa parceira e equipe | Autenticação e HTTPS passam a ser obrigatórios, não opcionais |
| Público pequeno e conhecido (dezenas de pessoas, no máximo) | Contas criadas pelo administrador; **sem cadastro aberto** |
| Não há servidor de e-mail | Sem recuperação de senha por e-mail; a redefinição é feita pelo administrador |
| Um único backend (FastAPI) e um único frontend (React) | Frontend e API podem ser servidos na **mesma origem**, o que simplifica cookies e CSRF |
| Os dados são fotos de armadilhas e medições, não dados pessoais sensíveis nem financeiros | Risco moderado; MFA fica para a Fase 2 (seção 12) |
| O nome da empresa parceira é sigiloso | A superfície pública não deve exibir nem vazar o nome |

---

# 3. Modelo de ameaça

Ameaças consideradas, o controle principal de cada uma e onde ele está descrito.

| Ameaça | Controle principal | Seção |
|---|---|---|
| Força bruta e *credential stuffing* no login | Senha longa, limite de tentativas por conta e por IP, bloqueio temporário | 5, 6 |
| Enumeração de contas (descobrir quais e-mails existem) | Resposta única e genérica, tempo de resposta equalizado | 6 |
| Vazamento do banco de dados | Senhas com Argon2id; tokens de sessão guardados só como hash | 4, 7 |
| Roubo de sessão por XSS | Cookie `HttpOnly`; nenhum token em `localStorage`; CSP | 7, 11 |
| CSRF (ação forjada a partir de outro site) | `SameSite=Strict` + token sincronizado + checagem de `Origin` | 8 |
| Fixação de sessão | Token novo a cada login; o servidor nunca aceita token escolhido pelo cliente | 7 |
| Interceptação na rede | HTTPS obrigatório, HSTS, cookie `Secure` | 10 |
| Acesso a endpoint esquecido sem proteção | Autenticação **por padrão** em todo o roteador, com teste que varre as rotas | 9 |
| Negação de serviço pelo bloqueio de conta | Bloqueio **temporário** e curto, nunca permanente; desbloqueio pelo administrador | 6 |
| Negação de serviço por senha gigante ou por inferência em excesso | Teto de tamanho da senha; limite de análises por usuário | 5, 9 |
| *Clickjacking* | `frame-ancestors 'none'` e `X-Frame-Options: DENY` | 10 |
| Segredo ou credencial padrão no repositório | Nenhum usuário nem senha padrão; primeira conta criada por comando interativo | 4, 9 |
| **Serviço interno exposto à internet** (banco, backend, painel, Docker) | Nenhuma porta publicada além de 80/443; rede interna isolada; firewall com negação por padrão; varredura externa obrigatória antes de publicar | 10.5, 10.7 |
| Banco com credencial fraca ou superusuário na aplicação | Usuário de aplicação com privilégio mínimo; senha forte vinda de variável de ambiente; `pg_hba` restrito à rede interna | 10.6 |

**Fora do alcance (risco aceito, seção 12):** atacante com acesso ao servidor ou
ao banco já comprometido, malware no dispositivo do usuário, engenharia social
e vulnerabilidades desconhecidas das dependências.

---

# 4. Decisões de arquitetura

## 4.1 Sessão de servidor com cookie, e não JWT

| Opção | Veredito | Motivo |
|---|---|---|
| **Sessão opaca no servidor, token em cookie `HttpOnly`** | **Adotada** | Revogação imediata (logout e troca de senha de fato encerram a sessão); o JavaScript não lê o token; não há chave de assinatura para proteger; é o padrão recomendado para aplicação web de uma só origem |
| JWT guardado em `localStorage` | Rejeitada | Qualquer XSS lê o token. O OWASP desaconselha: *qualquer JavaScript da origem acessa o armazenamento, então uma única falha de XSS expõe todos os tokens* |
| JWT em cookie `HttpOnly` | Rejeitada para o MVP | Resolve o XSS, mas a revogação exige uma lista de bloqueio no servidor, ou seja, volta a ser estado de servidor, com mais complexidade e sem ganho num backend único |
| HTTP Basic | Rejeitada | Reenvia a senha a cada requisição e não tem logout real |
| Provedor de identidade gerenciado (Keycloak, Auth0, Supabase Auth) | Alternativa válida, não adotada | Delegar é a opção mais segura em escala, mas adiciona infraestrutura ou dependência de terceiro para um protótipo pequeno. Reavaliar se surgirem MFA obrigatório, SSO ou muitos usuários |
| Login social (OAuth) | Não aplicável | Exige conta em terceiro e não atende a banca e a empresa com a mesma simplicidade |

**Nota sobre o tutorial do FastAPI:** a documentação oficial demonstra
OAuth2 + JWT (PyJWT, HS256). É um bom exemplo didático, mas guardar o JWT no
navegador herda o problema do XSS acima. Do tutorial adotamos o que continua
válido: hash de senha com **Argon2 via `pwdlib`** e a equalização de tempo com
um hash fictício para usuário inexistente (seção 6).

## 4.2 Mesma origem em produção

Em produção, o proxy reverso serve o frontend em `/` e a API em `/api` no
**mesmo domínio**. Efeitos: cookie `__Host-` possível, `SameSite=Strict`
viável, sem preflight de CORS no uso normal e superfície de CSRF menor. As
imagens de análise (`<img src="/api/analises/{id}/imagem">`) passam a enviar o
cookie sozinhas, o que protege os endpoints de mídia sem alterar o frontend.

Em desenvolvimento (`localhost:5173` chamando `localhost:8000`) as origens
diferem, mas continuam **no mesmo site** (a porta não conta para `SameSite`),
então o cookie funciona; é preciso `credentials: 'include'` no frontend e
`Access-Control-Allow-Credentials: true` com origem explícita, nunca `*`.

## 4.3 Autorização mínima

Existem dois papéis: gerente e operador. O servidor consulta o papel no banco
a cada requisição; não confia no corpo, no cookie nem no estado do frontend.
Operadores usam o sistema operacional; só gerente lista e cria contas.
O frontend apenas condiciona a navegação. Somente leitura fica para a Fase 2.
O banco admite zero ou um gerente, inclusive entre contas desativadas,
por CHECK de valores e índice único parcial WHERE papel = 'gerente'.
Nenhuma conta é promovida automaticamente.

---

# 5. Contas e senhas

## 5.1 Modelo de dados

Tabela `usuario` (substantivos de domínio em português, conforme a regra 8.2):

| Coluna | Tipo | Observação |
|---|---|---|
| `id` | `uuid` | PK |
| `email` | `varchar` | Único; normalizado (minúsculas, NFKC, sem espaços nas pontas) |
| `nome` | `varchar` | Exibição |
| `papel` | `varchar` | operador por padrão ou gerente; gerente único, inclusive inativo |
| `troca_senha_pendente` | `boolean` | false por padrão; true em criação pela API |
| `senha_hash` | `varchar` | String PHC do Argon2id (carrega algoritmo, parâmetros e sal) |
| `ativo` | `boolean` | Desativar bloqueia o login e revoga as sessões |
| `bloqueado_ate` | `timestamptz` nulo | Bloqueio temporário por tentativas (seção 6) |
| `senha_alterada_em` | `timestamptz` | Auditoria |
| `ultimo_login_em` | `timestamptz` nulo | Auditoria |
| `criado_em` | `timestamptz` | Padrão `now()` |

Tabela `sessao` (seção 7) e tabela `tentativa_login` (seção 6).

## 5.2 Política de senha

Segue NIST SP 800-63B-4 e OWASP Authentication Cheat Sheet, não regras antigas
de complexidade.

| Regra | Valor | Origem |
|---|---|---|
| Comprimento mínimo | **15 caracteres** (a senha é o único fator) | NIST 800-63B-4, 3.1.1.2; OWASP |
| Comprimento máximo aceito | **128 caracteres** (o padrão normativo é no mínimo 64; o teto evita abuso de CPU/memória) | NIST (≥ 64); decisão do projeto |
| Regras de composição (maiúscula, número, símbolo) | **Proibidas** | NIST: *SHALL NOT*; OWASP |
| Caracteres aceitos | Todos, inclusive Unicode e espaços; cada ponto de código conta como um caractere; normalizar em NFC antes do hash | NIST 3.1.1.2 |
| Truncamento | **Proibido** | OWASP |
| Troca periódica forçada | **Proibida**; só há troca por suspeita de comprometimento | NIST 3.1.1.2; OWASP |
| Lista de bloqueio | Rejeitar senha que conste de lista de senhas comuns ou vazadas, comparando a senha inteira, e informar o motivo | NIST 3.1.1.2 (obrigatório); OWASP |
| Senha contextual | Rejeitar a que **contém** o e-mail, a parte local do e-mail ou o nome do produto (`trapsight`), em qualquer caixa | Decisão do projeto; NIST recomenda palavras de contexto na lista de bloqueio |
| Padrões triviais | Rejeitar senha de um só caractere repetido ou de sequência crescente (`abcdefghijklmnopqrst`, `12345678901234567890`) | Decisão do projeto |
| Erro de política | `422` com código `SENHA_FRACA`; a resposta **nunca devolve a senha enviada** | Decisão do projeto |

**Lista mínima obrigatória:** a lista de bloqueio do sistema **deve conter, no mínimo,** todas as senhas de `security/pentest/senhas_bloqueadas_minimas.txt` (a suíte de invasão as testa). A implementação pode e deve ter uma lista bem maior.

**Lista de bloqueio:** arquivo local de senhas comuns versionado no repositório
(sem segredo nenhum, é dado público). Opcionalmente, consulta ao serviço
*Pwned Passwords* pelo modo de intervalo (*k-anonymity*: só os 5 primeiros
caracteres do SHA-1 saem do servidor), com falha aberta se o serviço estiver
fora do ar. A lista local é a obrigatória; a consulta externa é um acréscimo.

## 5.3 Armazenamento

| Item | Decisão |
|---|---|
| Algoritmo | **Argon2id**, via `pwdlib[argon2]` (o mesmo que a documentação do FastAPI recomenda) |
| Parâmetros mínimos | `m=19456 KiB` (19 MiB), `t=2`, `p=1`, ou equivalente OWASP (`m=46 MiB,t=1`; `m=12 MiB,t=3`). Calibrar no servidor real para algo em torno de 100 a 500 ms por hash |
| Verificação dos parâmetros | **Teste automatizado** lê a string PHC (`$argon2id$v=19$m=…,t=…,p=…`) do hash gerado e falha se ficar abaixo do mínimo. Não confiar apenas nos padrões da biblioteca |
| Sal | Único por senha, gerado pela biblioteca |
| *Pepper* | Não adotado na v1: adiciona um segredo a gerenciar e rotacionar sem ganho relevante neste cenário. Se adotado depois, segue a seção 3 de `security_spec.md` |
| Atualização | `check_needs_rehash` no login bem-sucedido: se os parâmetros mudaram, o hash é regravado |
| Em log, resposta ou erro | Nunca: nem a senha, nem o hash |

## 5.4 Gestão de contas pelo gerente e pela CLI

Comandos por `python -m src.cli` (executados no ambiente do backend):

| Comando | Função |
|---|---|
| `criar-usuario` | Pede e-mail e nome, lê a senha com `getpass` (sem eco, sem argumento de linha, sem variável de ambiente), aplica a política 5.2 |
| `redefinir-senha` | Mesma leitura segura; revoga todas as sessões do usuário |
| `desativar-usuario` / `ativar-usuario` | Revoga as sessões ao desativar |
| `desbloquear-usuario` | Zera `bloqueado_ate` e as tentativas |
| `listar-usuarios` | Mostra e-mail, ativo, último login (nunca o hash) |

**Sem usuário nem senha padrão**, em nenhum ambiente. O banco nasce vazio; a
primeira conta é criada com `criar-usuario`. O *seed* de demonstração não cria
credenciais.

---

### 5.4.1 Criação e listagem pela interface

POST /api/usuarios exige gerente, CSRF e origem válidos. O corpo JSON
estrito aceita apenas email (3–254 caracteres, endereço com parte local e
domínio), nome (1–120 após trim) e senha inicial no campo senha (1–1024
antes da política). Campos extras, inclusive papel, ativo e flag de troca,
geram 422 VALIDACAO_FALHOU. A política existente recebe nome e email
normalizado por NFKC, minúsculas e trim; falhas geram 422 SENHA_FRACA.
Colisões de email, inclusive Unicode/caixa, geram 409 EMAIL_JA_CADASTRADO.
Revelar duplicidade é aceitável porque só o gerente confiável usa a rota
e já pode listar essas contas.

A conta nasce operador ativo, sem sessão e com troca_senha_pendente=true.
POST responde 201 com id, email, nome, papel, ativo, ultimo_login_em e
criado_em. GET /api/usuarios exige gerente e devolve array dos mesmos campos
em ordem de email, sem paginação no MVP. Nunca senha ou hash.
As respostas usam Cache-Control: no-store.
Cada gerente pode criar até 20 contas por hora; CONTAS_POR_HORA configura esse
teto. O limite é contado por gerente, não por IP, e responde 429 LIMITE_CONTAS
com Retry-After quando esgotado.

Nos dois endpoints, anônimo recebe 401 NAO_AUTENTICADO, operador recebe
403 ACESSO_NEGADO e gerente recebe sucesso. Em métodos não seguros, a
verificação de CSRF/origem precede a autorização por papel.
Não existem operações de edição, exclusão, ativação, desativação ou
redefinição de senha na API. Auditoria: conta_criada com usuario_id e
criado_por_id (null para CLI), acesso_negado com usuario_id; nunca registrar
senha, hash ou corpo da requisição.

### 5.4.2 Atribuição de papel

Só a CLI concede gerente: criar-usuario --papel operador ou gerente
(padrão operador) e definir-papel --email ... --papel operador ou gerente.
Definir papel revoga todas as sessões da conta na mesma transação.
O CHECK só admite gerente/operador; o índice parcial impede segundo gerente
mesmo desativado. A colisão falha sem alterar contas ou sessões.
Para transferir a função, rebaixar o atual e depois promover o próximo
pela CLI. O primeiro gerente exige --papel gerente explicitamente.
Sem usuário ou senha padrão; o seed não cria credenciais.

### 5.4.3 Troca inicial obrigatória

troca_senha_pendente tem padrão false para contas existentes e criadas pela
CLI e true para contas criadas pela API. Login e /api/auth/me devolvem papel
e a flag no objeto usuario. Ambos são lidos do banco a cada requisição.
Enquanto pendente, o middleware só libera GET /api/auth/me,
POST /api/auth/senha e POST /api/auth/logout; qualquer outra rota sob /api
retorna 403 TROCA_DE_SENHA_OBRIGATORIA. OPTIONS conserva o tratamento CORS;
login permanece público com verificação de origem.
A troca exige senha atual, senha nova diferente da atual e política existente,
limpa a flag só após sucesso, revoga sessões anteriores e emite novo
cookie/CSRF. Falhas mantêm a flag. O frontend encaminha a conta para
/conta/senha antes de mostrar dados e consulta /auth/me após o sucesso.

---

# 6. Login

## 6.1 Contrato

`POST /api/auth/login`, corpo `{ "email": "...", "senha": "..." }`.

| Resultado | Resposta |
|---|---|
| Sucesso | `200` com usuario (id, email, nome, papel, troca_senha_pendente), csrf_token e Set-Cookie da sessão |
| Qualquer falha de credencial | `401` com código `CREDENCIAIS_INVALIDAS` e a mensagem **única** "E-mail ou senha inválidos." |
| Limite por IP excedido | `429` com `LIMITE_TENTATIVAS` e cabeçalho `Retry-After` |
| Corpo malformado | `422` `VALIDACAO_FALHOU` (padrão do projeto) |

A mesma resposta `401` vale para: e-mail inexistente, senha errada, conta
inativa e conta **bloqueada**. O cliente não consegue distinguir os casos
(OWASP: mesma mensagem e mesmo código HTTP para todas as falhas).

## 6.2 Ordem das verificações (anti-enumeração e anti-temporização)

1. Normalizar e-mail; validar formato e tamanho (e-mail ≤ 254, senha ≤ 128).
2. Checar o limite **por IP**; excedido, devolve `429`.
3. Buscar o usuário.
4. **Sempre** executar uma verificação de Argon2: contra o hash do usuário, ou
   contra um `HASH_FICTICIO` calculado na inicialização quando o usuário não
   existe. Assim o tempo de resposta não revela se a conta existe (técnica
   usada no tutorial do FastAPI).
5. Só **depois** consultar `ativo` e `bloqueado_ate`. Conta bloqueada recusa até
   a senha correta, para o atacante não saber quando acertou.
6. Registrar a tentativa (sucesso ou falha) em `tentativa_login`.
7. No sucesso: zerar o contador, regravar o hash se necessário, criar a sessão
   nova (seção 7) e responder.

## 6.3 Limites de tentativas

O OWASP e o NIST exigem limitação, mas não fixam números (o NIST só impõe o
teto máximo de 100 falhas consecutivas por autenticador). Os valores abaixo são
**decisão do projeto**, deliberadamente mais rígidos que o teto normativo, e
ficam em configuração.

| Controle | Valor padrão | Efeito |
|---|---|---|
| Por conta | **5 falhas em 15 min** | Bloqueio por **15 min** (`bloqueado_ate`); sucesso zera o contador |
| Por IP | **30 falhas em 15 min** | `429` com `Retry-After`; protege contra varredura de várias contas |
| Bloqueio permanente | **Nunca** | Evita que um terceiro tranque a conta de alguém para sempre; o administrador pode desbloquear |
| CAPTCHA | Não na v1 | Complexidade e dependência externa; reavaliar se houver ataque real |

**IP real atrás do proxy:** o backend só confia em `X-Forwarded-For` quando a
requisição vem do proxy reverso (configurar `--forwarded-allow-ips` com o
endereço do proxy). Confiar no cabeçalho de qualquer origem permite que o
atacante forje o IP e fuja do limite.

---

# 7. Sessão

## 7.1 Token e armazenamento

| Item | Decisão |
|---|---|
| Geração | `secrets.token_urlsafe(32)`: 256 bits de CSPRNG (o OWASP exige no mínimo 64 bits e recomenda 128 ou mais) |
| No banco | Apenas o **SHA-256** do token (`token_hash`). Quem lê o banco não consegue usar nenhuma sessão |
| Conteúdo do token | Aleatório e sem significado: nada de usuário, papel ou dado pessoal |
| Validação | O servidor só aceita tokens que existem em `sessao`; token desconhecido é recusado e registrado |

Tabela `sessao`: `id`, `usuario_id`, `token_hash` (único), `csrf_token`,
`criado_em`, `ultimo_uso_em`, `expira_em`, `revogada_em`, `ip`, `user_agent`.
`ip` e `user_agent` servem à auditoria e à tela futura de sessões ativas.

## 7.2 Cookie

```http
Set-Cookie: __Host-trapsight_sessao=<token>; Secure; HttpOnly; SameSite=Strict; Path=/
```

O cookie é **de sessão**, sem `Expires` nem `Max-Age`: o OWASP lembra que esses
atributos o tornam persistente em disco. Os prazos de 7.3 são aplicados pelo
servidor, que não depende do cookie para expirar a sessão.

| Atributo | Motivo |
|---|---|
| `Secure` | Só trafega em HTTPS |
| `HttpOnly` | JavaScript não lê; reduz o impacto de XSS |
| `SameSite=Strict` | Não vai em requisição originada em outro site. O SPA não é prejudicado: as chamadas à API partem da própria página, no mesmo site |
| `__Host-` | Exige `Secure`, `Path=/` e **proíbe** `Domain`: o cookie não vaza para subdomínios |
| Nome genérico | Não revela a tecnologia |
| Em desenvolvimento | `COOKIE_SECURE=false` e nome sem o prefixo, apenas quando `AMBIENTE=desenvolvimento` |

## 7.3 Ciclo de vida

| Regra | Valor |
|---|---|
| **Inatividade** | **30 min** (OWASP: 15 a 30 min para risco baixo) |
| **Duração absoluta** | **8 h** (OWASP: 4 a 8 h para um dia de trabalho) |
| Renovação do `ultimo_uso_em` | No máximo **1 vez por minuto** (ou a cada 1/5 do prazo de inatividade, o que for menor, para os prazos curtos da homologação), para não gravar a cada requisição |
| Aplicação dos prazos | **No servidor**, nunca por temporizador do cliente |
| Sessão nova | A cada login (token inédito, o antigo nunca é reaproveitado), o que elimina a fixação |
| Sessões simultâneas | Até **5** por usuário; a mais antiga é revogada ao exceder |
| Troca de senha | Revoga **todas** as outras sessões e emite uma nova para a atual |
| Desativar ou redefinir senha pelo administrador | Revoga todas as sessões |
| Logout | Marca `revogada_em` no servidor (apagar só o cookie não invalida um token roubado), limpa o cookie e envia `Cache-Control: no-store` |
| Limpeza | Remover sessões expiradas na inicialização e a cada login do usuário |

---

# 8. CSRF

Como a sessão vive em cookie, o navegador anexa o cookie a requisições de
qualquer site. Defesa em camadas, conforme o OWASP CSRF Prevention Cheat Sheet:

| Camada | Papel | Detalhe |
|---|---|---|
| **Token sincronizado** | Primária | O `csrf_token` é gerado com a sessão, devolvido no login e em `GET /api/auth/me`, e enviado pelo frontend no cabeçalho `X-CSRF-Token` em toda requisição `POST`, `PATCH`, `PUT` e `DELETE`. Comparação em tempo constante. Ausente ou diferente: `403` `CSRF_INVALIDO` |
| **Verificação de `Origin`** | Defesa em profundidade | Em métodos não seguros, o `Origin` (ou o `Referer`) precisa coincidir com a origem permitida; `Origin: null` ou ausente é recusado |
| `SameSite=Strict` | Defesa em profundidade | Seção 7.2. O OWASP lembra que complementa, mas não substitui, o token |
| CORS restrito | Complemento | Origens explícitas em `CORS_ORIGENS`, nunca `*` (exigência já existente na seção 7 de `security_spec.md`) |

Regras adicionais: **nunca** alterar estado com `GET`; o `csrf_token` fica
**somente em memória** no frontend (nunca em `localStorage`) e é recuperado
por `GET /api/auth/me` ao recarregar a página.

---

# 9. API: proteção, erros e abuso

## 9.1 Endpoints

| Método e rota | Auth | CSRF | Função |
|---|---|---|---|
| `POST /api/auth/login` | Não | Não (sem sessão ainda; protegido por limite, `Origin` e `SameSite`) | Cria a sessão |
| `POST /api/auth/logout` | Sim | Sim | Revoga a sessão |
| `GET /api/auth/me` | Sim | Não | Usuário atual e `csrf_token`; o SPA chama ao carregar |
| `POST /api/auth/senha` | Sim | Sim | Troca a própria senha (`senha_atual`, `senha_nova`); revoga as outras sessões |
| `GET /healthz` | Não | Não | Verificação de saúde, sem dados sensíveis |
| **Todos os demais `/api/*`** | **Sim** | Em métodos não seguros | `armadilhas`, `analises`, histórico, mídia |

## 9.2 Seguro por padrão

A dependência `usuario_atual` é aplicada **no roteador-raiz** da API, não rota
a rota. Rota nova nasce protegida; ser pública exige uma exceção explícita e
visível em código. Um **teste automatizado percorre `app.routes`** e falha se
alguma rota fora da lista de exceções responder diferente de `401` sem sessão.

## 9.3 Códigos de erro novos

Seguem o envelope existente (`{ "erro": { "codigo", "mensagem", "detalhes" } }`).

| Código | HTTP | Quando |
|---|---|---|
| `NAO_AUTENTICADO` | 401 | Sem sessão, sessão expirada ou revogada |
| `CREDENCIAIS_INVALIDAS` | 401 | Qualquer falha no login (seção 6.1) |
| `CSRF_INVALIDO` | 403 | Token ausente ou incorreto, `Origin` não permitido |
| `LIMITE_TENTATIVAS` | 429 | Limite por IP no login |
| `LIMITE_ANALISES` | 429 | Excesso de análises por usuário (9.4) |
| `LIMITE_CONTAS` | 429 | Excesso de criação de contas pelo gerente (5.4.1) |
| `SENHA_FRACA` | 422 | Política 5.2 violada, com o motivo em `detalhes` |

O frontend decide o comportamento **pelo código**, nunca pelo texto, como no
restante do projeto.

## 9.4 Limite de análises

A inferência é a operação mais cara do sistema e agora está exposta. Limite
inicial de **30 análises por minuto por usuário** (`LIMITE_ANALISES`),
configurável. Atende ao item pendente da seção 10.3 de `security_spec.md`.

## 9.5 Superfície de produção

| Controle | Detalhe |
|---|---|
| `/docs`, `/redoc` e `/openapi.json` | **Desativados** em produção (`AMBIENTE=producao`); o mapa completo da API não deve ser público |
| `uvicorn` | Sem cabeçalho `Server` identificável; `--proxy-headers` apenas com `--forwarded-allow-ips` restrito |
| Erros | Nunca expõem pilha, caminho ou SQL (já exigido em `security_spec.md`, seção 9) |

---

# 10. Hospedagem e transporte

## 10.1 Topologia

```text
Internet ──443──▶ Caddy (TLS, cabeçalhos) ──┬──▶ /api/*  → backend:8000
                                           └──▶ /*      → frontend estático
                        (rede interna do Compose, sem portas publicadas)
                                  backend ──▶ db:5432
```

| Item | Decisão |
|---|---|
| Proxy reverso | **Caddy**: HTTPS automático (Let's Encrypt), renovação sozinha, redirecionamento de HTTP para HTTPS |
| Portas expostas | **Somente 80 e 443**, no proxy. `backend`, `db` e `frontend` ficam só na rede interna do Compose |
| Frontend em produção | **Build estático** servido pelo proxy ou por um servidor mínimo. O servidor de desenvolvimento do Vite **não** vai a produção |
| Banco | Nunca publicado; senha forte vinda de variável de ambiente (seção 3 de `security_spec.md`) |
| Servidor | Firewall liberando só 80/443 e SSH (por chave, sem senha); atualizações de segurança do sistema operacional ativas |
| Arquivo Compose | `docker-compose.prod.yml` separado, sem *bind mounts* de código |

## 10.2 Cabeçalhos de segurança (no proxy)

Valores conforme o OWASP HTTP Headers Cheat Sheet.

| Cabeçalho | Valor |
|---|---|
| `Strict-Transport-Security` | `max-age=63072000; includeSubDomains`. **Sem `preload` no início:** é compromisso difícil de desfazer; só depois de o domínio estar estável |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` (e `frame-ancestors 'none'` na CSP) |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | `geolocation=(), camera=(), microphone=()` |
| `Cache-Control` | `no-store` nas respostas de `/api/auth/*` |
| `Server` e `X-Powered-By` | Removidos |
| `Content-Security-Policy` | Ver 10.3 |

## 10.3 Content-Security-Policy

Ponto de partida:

```text
default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';
img-src 'self' data:; connect-src 'self'; frame-ancestors 'none';
base-uri 'self'; form-action 'self'
```

- `script-src 'self'` sem `unsafe-inline`: é a parte que realmente barra XSS.
- `style-src 'unsafe-inline'` é uma **concessão documentada**: a biblioteca de
  gráficos (Recharts) aplica estilos em linha em SVG. Reavaliar quando houver
  alternativa.
- Publicar primeiro como `Content-Security-Policy-Report-Only`, ajustar e só
  então aplicar. O OWASP avisa que a CSP é complexa de manter.

## 10.4 Alterações necessárias no frontend em produção

`VITE_API_URL` passa a ser o caminho relativo `/api`. O módulo de mídia hoje
exige URL absoluta (`new URL(API_URL)`); ele precisa aceitar caminho relativo
na mesma origem.

## 10.5 Regra de exposição zero

Esta seção é **obrigatória e inegociável**. Qualquer item abaixo violado
bloqueia a publicação.

| # | Regra | Como se comprova |
|---|---|---|
| 1 | **O banco de dados nunca é alcançável de fora do Compose.** O serviço `db` não tem a chave `ports:` e não está em nenhuma rede publicada | Varredura externa de todas as portas TCP (1 a 65535) mostra a **5432 fechada**; teste de conexão direta ao Postgres falha |
| 2 | **Só o proxy publica portas, e só 80 e 443.** `backend`, `frontend` e `db` usam `expose:` (rede interna) ou nada | A varredura externa lista **apenas 80 e 443** (e a porta de SSH, restrita por origem, se existir). Qualquer outra porta aberta reprova |
| 3 | **Nenhuma porta de administração ou depuração aberta:** Docker (2375/2376), Redis, MongoDB, MySQL, Elasticsearch, Prometheus, painéis, `pgAdmin`, depurador | Mesma varredura, mais a lista de portas sensíveis da suíte |
| 4 | **Nunca montar o socket do Docker** (`/var/run/docker.sock`) em nenhum contêiner, nem usar `privileged: true`, `network_mode: host` ou `cap_add` sem justificativa escrita | Análise de configuração (Trivy/hadolint) e revisão do Compose |
| 5 | **Nenhum arquivo sensível servido pelo proxy:** `.env`, `.git/`, `backend/`, `uploads/`, mapas de código-fonte (`*.map`), listagem de diretório, backups | Testes de caminhos sensíveis da suíte e varredura de exposições (Nuclei) |
| 6 | **Uploads nunca servidos como arquivos estáticos.** Só passam pelo endpoint autenticado, com cabeçalhos seguros | Teste de acesso direto ao diretório e aos caminhos de upload sem sessão |
| 7 | **Documentação interativa fechada** (`/docs`, `/redoc`, `/openapi.json`) e **nenhum endpoint de métricas, de depuração ou de saúde detalhada** público | Testes de vazamento de informação |
| 8 | **Firewall do servidor com negação por padrão:** entrada liberada só para 80/443 (e SSH por chave, limitado à origem do administrador). A regra do Docker não pode contornar o firewall do host | Varredura externa; revisão das regras (`iptables`/`nftables`/grupo de segurança do provedor) |
| 9 | **Segredos só em variáveis de ambiente** do servidor, fora do repositório, das imagens e dos logs (seção 3 de `security_spec.md`) | Varredura de segredos no repositório e no histórico (gitleaks, Trivy) |
| 10 | **Sem credencial padrão em lugar nenhum** (banco, contas, painéis) | Teste de credenciais padrão (Nuclei `default-logins`) e testes de login da suíte |

**Armadilha conhecida do Docker:** `ports: "5432:5432"` publica a porta em
**todas as interfaces** (`0.0.0.0`), e o Docker escreve suas próprias regras de
firewall, que **contornam** `ufw` e ferramentas semelhantes. Por isso o
firewall do **provedor** (grupo de segurança) é a camada confiável e a
varredura **externa** é a prova. Em desenvolvimento, quando for preciso
publicar uma porta, vincular sempre a `127.0.0.1` (como o `docker-compose.yml`
atual já faz).

## 10.6 Endurecimento do banco de dados e dos contêineres

| Item | Regra |
|---|---|
| Acesso ao Postgres | Somente pela rede interna do Compose, a partir do contêiner do backend |
| Usuário da aplicação | **Não é o superusuário.** Papel com `CONNECT` no banco e `SELECT/INSERT/UPDATE/DELETE` nas tabelas da aplicação; sem `CREATEDB`, `CREATEROLE`, `SUPERUSER`. As migrations rodam com um papel separado |
| Senha do banco | Gerada (mínimo 32 caracteres aleatórios), **única por ambiente**, só em variável de ambiente; nunca `postgres/postgres`, nunca `root/root` fora do desenvolvimento local |
| `pg_hba.conf` | Aceita apenas a rede interna do Compose, com `scram-sha-256`; nada de `trust` nem de `0.0.0.0/0` |
| Volume do banco | Volume nomeado, sem *bind mount* para diretório compartilhado |
| Backups | Cópia periódica (`pg_dump`) **fora do servidor web**, com acesso restrito e, se sair da máquina, criptografada |
| Contêineres | Usuário não-root (já em `security_spec.md`, 10.1), sistema de arquivos somente leitura quando possível, `no-new-privileges`, sem capacidades extras, limites de memória e CPU |
| Imagens | Bases mínimas, versão fixa (nunca `latest` em produção), varredura de vulnerabilidades antes de cada publicação |

## 10.7 Verificação antes de publicar

Antes de **cada** publicação, e depois a cada mudança de infraestrutura ou de
dependência:

1. Rodar a suíte completa de `../../validation/seguranca_testes.md` contra o
   ambiente de **homologação**, uma cópia descartável com a mesma configuração
   do definitivo.
2. Rodar a varredura de portas e o teste de TLS contra o ambiente **definitivo**
   (somente leitura, sem ataque ativo).
3. Arquivar o relatório (data, versão do código, resultado, exceções
   justificadas). **Falha crítica ou alta bloqueia a publicação.**
4. Se algo mudar na superfície (nova porta, novo serviço, nova rota pública), a
   suíte é atualizada **na mesma entrega**.
5. Quem implementa o sistema **apenas executa** a suíte, pelo executor cego
   (`security/scans/executar_cego.sh`): o relatório sai **cifrado** e só o
   revisor o abre. A seção 11 de `../../validation/seguranca_testes.md` explica
   a separação de funções.

---

# 11. Frontend

| Item | Regra |
|---|---|
| Rota `/login` | Pública; as demais exigem sessão |
| Estado de autenticação | Contexto React carregado por `GET /api/auth/me` ao abrir o app; enquanto carrega, não exibe conteúdo protegido nem redireciona |
| Guarda de rota | Sem sessão, redireciona para `/login` preservando o destino; após o login, volta a ele |
| `fetch` | `credentials: 'same-origin'` em produção (`'include'` em desenvolvimento); anexa `X-CSRF-Token` em métodos não seguros |
| Resposta `401` `NAO_AUTENTICADO` | Limpa o estado e leva ao login com aviso de sessão expirada; **não** repete a requisição em laço |
| Armazenamento | **Nada** de token, senha ou `csrf_token` em `localStorage` ou `sessionStorage` |
| Formulário | `type="password"`, `autocomplete="username"` e `"current-password"`, **colagem permitida** (gerenciadores de senha), botão desabilitado durante o envio, erro em `role="alert"` com o texto único "E-mail ou senha inválidos." |
| Troca de senha | `autocomplete="new-password"`; indicador de força opcional (zxcvbn-ts, conforme OWASP), sem regras de composição |
| Logout | Botão visível no cabeçalho em todas as telas |
| Cache | Ao sair, descartar dados em memória da sessão |
| XSS | Nenhum `dangerouslySetInnerHTML` com dado da API (regra existente na seção 11 de `security_spec.md`) |

---

# 12. Auditoria, riscos aceitos e Fase 2

## 12.1 Registro de eventos

Log estruturado, **sem** senha, hash, token nem `csrf_token`. Registrar:
login com sucesso e com falha, bloqueio de conta, limite por IP, logout, troca
e redefinição de senha, revogação de sessão, token desconhecido, `CSRF_INVALIDO`
e acessos negados. Identificar o usuário pelo `id`; para e-mail inexistente,
registrar apenas um hash curto, nunca o e-mail digitado, para não gravar
senhas digitadas no campo errado. Os logs são revisados quando houver
suspeita de ataque (OWASP: monitorar falhas de autenticação).

## 12.2 Riscos aceitos na v1

| Risco | Por que se aceita | Mitigação atual |
|---|---|---|
| **Sem MFA** | O OWASP considera o MFA a melhor defesa contra ataques a senhas, mas exige fluxo de cadastro do segundo fator e recuperação | Senha mínima de 15 caracteres + lista de bloqueio + limites de tentativa. É o patamar que o NIST define para um fator só |
| Sem recuperação de senha por e-mail | Não há servidor de e-mail; o público é pequeno | Redefinição pelo administrador via CLI |
| Criação de contas pelo gerente | Necessária à operação; gerente é confiável | Papel do banco, CSRF, corpo estrito, gerente único e auditoria |
| Sem CAPTCHA nem WAF | Dependência e custo desproporcionais | Limites por conta e por IP; Caddy e firewall |
| Bloqueio temporário permite incomodar uma conta alvo | Preferível ao bloqueio permanente | 15 min de duração; desbloqueio pelo administrador |
| Sem teste de intrusão independente | Fora do escopo acadêmico | Testes automatizados de segurança (seção 14) e este documento |

## 12.3 Fase 2 (gatilhos para revisar)

- **MFA por TOTP** (aplicativo autenticador), obrigatório se entrarem dados
  reais da empresa parceira em volume. No fluxo inicial do gerente, o risco
  de fator único é aceito com senha forte, CSRF, autorização e limites.
- Papel somente leitura e permissões adicionais.
- Tela de sessões ativas e de histórico de login.
- Recuperação de senha por e-mail, com token de uso único e expiração curta.
- Provedor de identidade gerenciado, se houver SSO ou crescimento de usuários.
- Verificação periódica de dependências (`pip-audit`, `npm audit`) a cada
  entrega relevante.

---

# 13. Documentos afetados (atualizados em 2026-10-16)

| Documento | Alteração |
|---|---|
| `../../rules/security_spec.md` | Seção 4 deixa de ser "risco aceito" e passa a apontar para este documento; ajustar 2.1, 2.3 e 10.3 (autenticação, HTTPS e limite de análises saem de "Fase 2") |
| `project_overview.md` | Seção 5.2: autenticação sai de "fora de escopo" e entra como requisito da hospedagem |
| `tech_stack.md` | Linha "Deploy: fora do escopo" passa a descrever Caddy + Compose de produção; acrescentar `pwdlib[argon2]` (dependência nova, exige confirmação conforme a regra 4.2 de `ai_development_rules.md`) |
| `../api/api_spec.md` | Endpoints `/api/auth/*`, códigos de erro da seção 9.3, cabeçalho `X-CSRF-Token` e cookie de sessão; remover "autenticação fora do escopo" |
| `../data/data_model.md` | Tabelas `usuario`, `sessao` e `tentativa_login` |
| `../frontend/telas_spec.md` | Nova tela `/login`, botão de logout e comportamento de sessão expirada; remover "autenticação" de fora do escopo |
| `../../../README.md` | Seção de execução e hospedagem; status |
| `../../validation/seguranca_testes.md` | **Criado** junto com este documento: especificação dos testes de invasão |
| `../../../.gitignore` | Ignorar `security/reports/` (relatórios podem conter dados da superfície e evidências) |

---

# 14. Testes de segurança obrigatórios

Dois níveis complementares:

- **Testes de unidade e integração do backend** (tabela abaixo), escritos junto
  com o código, rodam na pipeline normal (`pytest`).
- **Testes de invasão** (caixa-preta contra o sistema em execução, mais
  varreduras com ferramentas do mercado), especificados em
  `../../validation/seguranca_testes.md` e implementados em `security/`.
  **Rodam antes de toda publicação** (seção 10.7).

| Área | O que o teste prova |
|---|---|
| Rotas protegidas | Toda rota fora da lista de exceções responde `401` sem sessão (varre `app.routes`) |
| Anti-enumeração | E-mail inexistente, senha errada, conta inativa e conta bloqueada produzem **resposta idêntica** (status, código, mensagem); a verificação de Argon2 roda nos dois caminhos |
| Bloqueio | 5 falhas bloqueiam; durante o bloqueio, **a senha correta também falha**; expirado o prazo, entra |
| Limite por IP | A 31ª falha em 15 min retorna `429` com `Retry-After`; `X-Forwarded-For` de origem não confiável é ignorado |
| Política de senha | 14 caracteres rejeitados; 15 aceitos; senha da lista de bloqueio rejeitada; 129 caracteres rejeitados; Unicode aceito; sem exigência de composição |
| Hash | A string PHC é `argon2id` com `m`, `t` e `p` iguais ou acima do mínimo; senha nunca aparece em log nem resposta; rehash quando os parâmetros mudam |
| Cookie | `Secure`, `HttpOnly`, `SameSite=Strict`, `Path=/`, sem `Domain` e com o prefixo `__Host-` em produção |
| Sessão | Token novo a cada login (sem fixação); logout invalida **no servidor** (o cookie antigo recebe `401`); expiram por inatividade e por duração absoluta; troca de senha revoga as demais; o 6º login revoga o mais antigo |
| Banco | `sessao.token_hash` nunca contém o token em claro |
| CSRF | Método não seguro sem `X-CSRF-Token`, com token errado ou com `Origin` estranho retorna `403` |
| CORS | Nunca `*` com credenciais |
| Produção | `/docs` e `/openapi.json` retornam `404`; cabeçalhos da seção 10.2 presentes; `Server` ausente |
| Frontend | Guarda de rota; `401` leva ao login; nenhum dado de autenticação em `localStorage`; erro genérico exibido |

---

# 15. Plano de implementação sugerido

Ordem proposta, cada item como task própria, a ser detalhada depois da
aprovação deste documento:

1. **Dados:** migrations de `usuario`, `sessao` e `tentativa_login`.
2. **Senhas:** módulo de hash (Argon2id), política, lista de bloqueio e testes.
3. **Sessão e login:** serviço de sessão, endpoints `/api/auth/*`, limites e bloqueio.
4. **Proteção global:** dependência no roteador-raiz, CSRF, teste de varredura de rotas.
5. **CLI de contas:** criar, redefinir, desativar, desbloquear, listar.
6. **Limite de análises** e desativação de `/docs` em produção.
7. **Frontend:** `/login`, contexto de autenticação, guarda de rota, CSRF, logout, `401`.
8. **Hospedagem:** `docker-compose.prod.yml`, Caddy, build estático do frontend, cabeçalhos e CSP em modo de relatório.
9. **Verificação final:** executar a suíte de invasão (`security/`) contra a homologação e a varredura de portas contra o definitivo, arquivar o relatório e atualizar os documentos da seção 13.

A suíte de invasão **já existe antes do código**: ela é o critério de aceite
dos itens 3 a 8. Antes da implementação ela **falha de propósito** (por exemplo,
rotas abertas sem sessão); cada item implementado deve fazer os testes
correspondentes passarem.

---

# 16. Referências

Consultadas em outubro de 2026.

- OWASP, [Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html): comprimento, mensagens genéricas, enumeração, limitação, MFA, HTTPS.
- OWASP, [Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html): entropia do identificador, atributos do cookie, `__Host-`, regeneração, tempos de expiração, logout, por que não usar `localStorage`.
- OWASP, [Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html): parâmetros mínimos do Argon2id, sal, *pepper*, atualização no login.
- OWASP, [Cross-Site Request Forgery Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html): token sincronizado, `SameSite`, `Origin`, Fetch Metadata.
- OWASP, [HTTP Headers Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html): valores recomendados de cabeçalhos de segurança.
- NIST, [SP 800-63B-4, Digital Identity Guidelines: Authentication and Authenticator Management](https://pages.nist.gov/800-63-4/sp800-63b.html), seções 3.1.1 e 3.2.2: tamanho de senha, composição, lista de bloqueio, rotação, limitação.
- FastAPI, [OAuth2 com JWT](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/): `pwdlib` com Argon2 e equalização de tempo para usuário inexistente.
- OWASP, [Web Security Testing Guide v4.2](https://wstg.owasp.org/v4.2/4-Web_Application_Security_Testing/): catálogo de testes de invasão usado para organizar a suíte (`../../validation/seguranca_testes.md`).
- OWASP, [Application Security Verification Standard 5.0](https://owasp.org/www-project-application-security-verification-standard/), capítulos de autenticação, sessão e autorização: critérios de verificação.
- ZAP, [scans em Docker](https://www.zaproxy.org/docs/docker/): *baseline*, *full* e *API scan*.

**Conferido na implementação (2026-10-17):** o Argon2id é configurado com
parâmetros explícitos (19456 KiB, 2 iterações, 1 de paralelismo), sem depender
dos padrões de `PasswordHash.recommended()`; um teste lê os parâmetros da string
PHC e outro confirma a regravação do hash quando eles mudam. O IP do cliente vem
do `uvicorn --proxy-headers` com `FORWARDED_ALLOW_IPS` restrito ao endereço fixo
do proxy. **Ainda não verificado:** o formato do serviço *Pwned Passwords*, que
não é usado (a lista de bloqueio é local).

---

# FIM DO LOGIN
