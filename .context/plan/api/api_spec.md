# API — Projeto Integrador

**Versão:** 1.0
**Status:** ATIVO
**Escopo:** contrato REST entre frontend e backend

---

# 1. Objetivo

Especificar os endpoints da API. Cada endpoint existe para atender uma tela
descrita em `../frontend/telas_spec.md` — a API não expõe nada que a
interface não consuma.

---

# 2. Convenções

| Item | Convenção |
|---|---|
| Formato | JSON, exceto no upload de imagem (`multipart/form-data`) |
| Prefixo | `/api` |
| Identificadores | `uuid` |
| Datas | ISO 8601 com timezone (`2026-08-21T14:30:00Z`) |
| Percentuais | Número decimal de 0 a 100, duas casas |
| Nomes de campo | `snake_case` |

## 2.1 Códigos de status

| Código | Uso |
|---|---|
| `200` | Sucesso em leitura ou atualização |
| `201` | Recurso criado |
| `400` | Requisição malformada ou arquivo inválido |
| `401` | Sem sessão válida ou credenciais inválidas |
| `403` | CSRF inválido, papel insuficiente ou troca de senha pendente |
| `404` | Recurso não encontrado |
| `409` | Conflito de estado — ex.: análise em armadilha sem refil ativo |
| `413` | Arquivo acima do limite de tamanho |
| `422` | Falha de validação de campo |
| `429` | Limite de tentativas de login ou de análises excedido |
| `500` | Falha na inferência ou erro interno |

## 2.2 Formato de erro

Toda resposta de erro usa o mesmo corpo, em qualquer endpoint:

```json
{
  "erro": {
    "codigo": "REFIL_ATIVO_INEXISTENTE",
    "mensagem": "A armadilha não possui refil ativo.",
    "detalhes": { "armadilha_id": "3f2a..." }
  }
}
```

| Campo | Obrigatório | Descrição |
|---|---|---|
| `codigo` | Sim | Identificador estável em maiúsculas, usado pelo frontend para decidir o comportamento |
| `mensagem` | Sim | Texto em português, exibível ao usuário |
| `detalhes` | Não | Objeto com contexto adicional; ausente quando não houver |

O frontend deve reagir ao `codigo`, nunca ao texto da `mensagem` — mensagens
podem ser reescritas sem aviso, códigos não.

## 2.3 Códigos de erro

| Código | HTTP | Situação |
|---|---|---|
| `ARMADILHA_NAO_ENCONTRADA` | 404 | `armadilha_id` inexistente |
| `ANALISE_NAO_ENCONTRADA` | 404 | `analise_id` inexistente |
| `REFIL_ATIVO_INEXISTENTE` | 409 | Tentativa de análise em armadilha sem refil ativo |
| `IDENTIFICADOR_DUPLICADO` | 409 | Já existe armadilha com o mesmo `identificador` |
| `ARQUIVO_AUSENTE` | 400 | Campo `imagem` não enviado |
| `FORMATO_NAO_SUPORTADO` | 400 | Arquivo não é JPEG ou PNG |
| `RESOLUCAO_INSUFICIENTE` | 400 | Menor que 512 px no maior lado |
| `ARQUIVO_MUITO_GRANDE` | 413 | Acima de 4 MB ou de 20 milhões de pixels; `detalhes.motivo` é `bytes` ou `pixels` |
| `VALIDACAO_FALHOU` | 422 | Campo obrigatório ausente ou inválido |
| `PLACA_NAO_DETECTADA` | 500 | Modelo não localizou a superfície adesiva |
| `FALHA_INFERENCIA` | 500 | Erro durante a execução do modelo |
| `REQUISICAO_INVALIDA` | 400 | Requisição rejeitada pelo framework antes de chegar à rota (ex.: corpo multipart malformado) |
| `ROTA_NAO_ENCONTRADA` | 404 | Rota inexistente |
| `METODO_NAO_PERMITIDO` | 405 | Método HTTP não aceito pela rota |
| `ERRO_INTERNO` | 500 | Falha inesperada; a mensagem é genérica e o detalhe fica só no log do servidor |
| `NAO_AUTENTICADO` | 401 | Sem sessão, sessão expirada ou revogada |
| `CREDENCIAIS_INVALIDAS` | 401 | Qualquer falha de login (conta inexistente, senha errada, conta inativa **ou bloqueada**): resposta única, sem distinguir o motivo; também a senha atual errada na troca de senha |
| `CSRF_INVALIDO` | 403 | Token `X-CSRF-Token` ausente ou incorreto, ou `Origin` não permitido |
| `LIMITE_TENTATIVAS` | 429 | Limite de falhas de login por IP; traz `Retry-After` |
| `LIMITE_ANALISES` | 429 | Excesso de análises por usuário; traz `Retry-After` |
| `LIMITE_CONTAS` | 429 | Excesso de criação de contas pelo gerente; traz `Retry-After` |
| `SENHA_FRACA` | 422 | Senha fora da política (`login.md`, 5.2); o motivo vai em `detalhes` e a senha **nunca** é devolvida |
| `ACESSO_NEGADO` | 403 | Papel atual do banco não autoriza a operação |
| `EMAIL_JA_CADASTRADO` | 409 | E-mail normalizado duplicado; somente gerente |
| `TROCA_DE_SENHA_OBRIGATORIA` | 403 | Conta deve substituir a senha inicial |

## 2.4 Restrições de upload

| Restrição | Valor |
|---|---|
| Tamanho máximo | 4 MB (a hospedagem na Vercel limita o corpo da requisição a 4,5 MiB) |
| Formatos aceitos | JPEG, PNG |
| Resolução mínima | 512 px no maior lado |
| Resolução máxima | 20 milhões de pixels decodificados — protege contra *decompression bomb*; acima disso a resposta é `413` `ARQUIVO_MUITO_GRANDE`. Dentro do limite, a imagem é redimensionada no pré-processamento |

O mínimo de 512 px decorre da resolução de entrada do modelo, definida em
`../model/modelo_spec.md`, seção 6. Imagens menores seriam ampliadas, sem
ganho real de informação e com perda de precisão na segmentação.

O `413` traz `detalhes.motivo`: `bytes` quando o arquivo passa de 4 MB e
`pixels` quando as dimensões decodificadas passam do teto. O frontend usa o
motivo para escolher a mensagem; clientes que o ignoram continuam
funcionando.

## 2.5 Modo de execução da inferência

A inferência é **síncrona**. A requisição permanece aberta até a conclusão.

| Item | Valor |
|---|---|
| Timeout | 30 segundos |
| Tempo esperado em CPU | 1 a 3 segundos por imagem |

Processamento assíncrono com fila e polling foi descartado: exigiria
infraestrutura adicional e complexidade no frontend para um ganho inexistente
na escala do MVP, onde as análises são enviadas uma a uma, manualmente.

Caso o tempo de resposta medido ultrapasse 10 segundos de forma consistente, a
decisão deve ser reavaliada.

## 2.6 CORS e variáveis de ambiente

**CORS:** origem permitida definida pela variável `CORS_ORIGENS`, aceitando
lista separada por vírgula. Em desenvolvimento, `http://localhost:5173`
— porta padrão do Vite. Com a sessão em cookie, o CORS precisa liberar
credenciais (`Access-Control-Allow-Credentials: true`) com origem **explícita**,
nunca `*`. Em produção, API e frontend ficam na **mesma origem** (`/api`), o que
dispensa CORS no uso normal (`login.md`, 4.2).

**Variáveis de ambiente do backend:**

| Variável | Exemplo | Obrigatória |
|---|---|---|
| `DATABASE_URL` | `postgresql://user:senha@db:5432/armadilhas` | Sim |
| `MODEL_WEIGHTS_PATH` | `/app/models/checkpoints/latest.pt` | Sim |
| `MODEL_VERSION` | `v0.1.0-dev` | Sim |
| `UPLOADS_DIR` | `/app/data/uploads` | Sim |
| `CORS_ORIGENS` | `http://localhost:5173` | Sim |
| `LIMIAR_ATENCAO` | `10` | Não — padrão 10 |
| `LIMIAR_TROCAR` | `20` | Não — padrão 20 |
| `FUSO_PRODUTO` | `America/Sao_Paulo` | Não — zona IANA da data civil que conta os dias em uso |
| `AMBIENTE` | `producao` | Sim — `desenvolvimento`, `homologacao` ou `producao`; em `producao` a documentação interativa (`/docs`, `/redoc`, `/openapi.json`) é desativada |
| `COOKIE_SECURE` | `true` | Não — padrão `true`; `false` só com `AMBIENTE=desenvolvimento` |
| `SESSAO_INATIVIDADE_SEGUNDOS` | `1800` | Não — padrão 1800 (30 min) |
| `SESSAO_DURACAO_MAXIMA_SEGUNDOS` | `28800` | Não — padrão 28800 (8 h) |
| `SESSAO_MAXIMA_POR_USUARIO` | `5` | Não — padrão 5 |
| `LOGIN_FALHAS_POR_CONTA` | `5` | Não — padrão 5 em `LOGIN_JANELA_SEGUNDOS` |
| `LOGIN_BLOQUEIO_SEGUNDOS` | `900` | Não — padrão 900 (15 min) |
| `LOGIN_FALHAS_POR_IP` | `30` | Não — padrão 30 em `LOGIN_JANELA_SEGUNDOS` |
| `LOGIN_JANELA_SEGUNDOS` | `900` | Não — padrão 900 (15 min) |
| `ANALISES_POR_MINUTO` | `30` | Não — padrão 30 por usuário |
| `CONTAS_POR_HORA` | `20` | Não — padrão 20 por gerente |
| `ARGON2_MEMORIA_KIB` | `19456` | Não — padrão 19456 (19 MiB), mínimo do OWASP |
| `ARGON2_ITERACOES` | `2` | Não — padrão 2 |
| `ARGON2_PARALELISMO` | `1` | Não — padrão 1 |
| `FORWARDED_ALLOW_IPS` | `172.20.0.0/16` | Sim em produção — só deste endereço (o proxy) o `X-Forwarded-For` é confiável |

Prazos e limites são variáveis de ambiente para a homologação poder usar valores
curtos nos testes de expiração e de limite (`../../security/README.md`).

**Variáveis do frontend:**

| Variável | Exemplo |
|---|---|
| `VITE_API_URL` | `http://localhost:8000/api` em desenvolvimento; `/api` em produção (mesma origem) |

Os limiares são variáveis de ambiente porque serão recalibrados com dados
reais, conforme `../foundation/project_overview.md`, seção 7.2. Fixá-los no
código exigiria alteração e novo build a cada ajuste.

## 2.7 Autenticação e sessão

Todas as rotas `/api/*` **exigem sessão**, exceto `POST /api/auth/login`. A
autenticação é aplicada no roteador-raiz: rota nova nasce protegida
(`login.md`, 9.2).

| Item | Regra |
|---|---|
| Cookie de sessão | `__Host-trapsight_sessao` em produção (em desenvolvimento, `trapsight_sessao`), `Secure`, `HttpOnly`, `SameSite=Strict`, `Path=/`, sem `Domain` e sem `Max-Age` |
| Token CSRF | Devolvido em `csrf_token` no login e em `GET /api/auth/me`; enviado em `X-CSRF-Token` em todo `POST`, `PATCH`, `PUT` e `DELETE` |
| `Origin` | Em métodos não seguros precisa coincidir com a origem permitida; ausente ou `null` é recusado (`403 CSRF_INVALIDO`) |
| Respostas de autenticação | Sempre com `Cache-Control: no-store` |
| Sem sessão | `401 NAO_AUTENTICADO` em toda rota protegida, **antes** de validar o corpo ou buscar o recurso: um id inexistente sem sessão responde `401`, nunca `404` nem `422` |

---

# 3. Mapa de endpoints

| Método | Rota | Tela que atende |
|---|---|---|
| `GET` | `/api/armadilhas` | Dashboard |
| `GET` | `/api/modelos-armadilha` | Cadastro (escolha do modelo) |
| `POST` | `/api/armadilhas` | Cadastro |
| `GET` | `/api/armadilhas/{id}` | Detalhe |
| `PATCH` | `/api/armadilhas/{id}` | Cadastro (edição) |
| `DELETE` | `/api/armadilhas/{id}` | Detalhe (remoção) |
| `PUT`, `DELETE`, `GET` | `/api/armadilhas/{id}/foto` | Cadastro e edição, cartão e detalhe (foto de identificação) |
| `POST` | `/api/armadilhas/{id}/refis` | Detalhe (troca de refil) |
| `GET` | `/api/armadilhas/{id}/analises` | Detalhe (gráfico e histórico) |
| `POST` | `/api/analises` | Nova análise |
| `GET` | `/api/analises/{id}` | Nova análise (resultado) |
| `GET` | `/api/analises/{id}/imagem` e `/mascara` | Imagem: Nova análise e Detalhe. A máscara não é consumida pela interface |
| `POST` | `/api/auth/login` | Login |
| `POST` | `/api/auth/logout` | Cabeçalho (sair) |
| `GET` | `/api/auth/me` | Carga inicial do aplicativo |
| `POST` | `/api/auth/senha` | Alterar senha |
| `GET` | `/api/usuarios` | Contas (somente gerente) |
| `POST` | `/api/usuarios` | Criar operador (somente gerente) |
| `GET` | `/healthz` | Verificação de saúde (sem dados sensíveis, fora de `/api`) |

## 3.1 Endpoints de autenticação

**`POST /api/auth/login`** — corpo `{ "email": "...", "senha": "..." }` (e-mail até
254 caracteres, senha até 128).

- `200`: usuario (id, email, nome, papel, troca_senha_pendente), csrf_token e Set-Cookie
  da sessão (token novo a cada login).
- `401 CREDENCIAIS_INVALIDAS` com a mensagem única "E-mail ou senha inválidos." para
  qualquer falha de credencial, conta inativa ou bloqueada.
- `429 LIMITE_TENTATIVAS` com `Retry-After`; `403 CSRF_INVALIDO` com `Origin` hostil;
  `422 VALIDACAO_FALHOU` para corpo malformado.

**`POST /api/auth/logout`** — exige sessão e `X-CSRF-Token`. `204`; revoga a sessão
**no servidor** e limpa o cookie.

**`GET /api/auth/me`** — exige sessão. `200`:
usuario (id, email, nome, papel, troca_senha_pendente) e csrf_token; `401 NAO_AUTENTICADO`
sem sessão. O aplicativo o chama ao carregar para recuperar o estado.

**`POST /api/auth/senha`** — exige sessão e `X-CSRF-Token`. Corpo
`{ "senha_atual": "...", "senha_nova": "..." }`.

- `200`: `{ "csrf_token": "..." }` e `Set-Cookie` de uma sessão **nova**; todas as
  outras sessões do usuário são revogadas.
- `401 CREDENCIAIS_INVALIDAS` se a senha atual estiver errada; `422 SENHA_FRACA` se
  a nova violar a política (`login.md`, 5.2) ou for igual à senha atual. Neste
  último caso, detalhes.motivo é `igual_atual`.

---

## 3.2 Contas de usuário

GET e POST /api/usuarios exigem gerente: anônimo recebe 401 NAO_AUTENTICADO
e operador, 403 ACESSO_NEGADO. POST exige CSRF e origem válidos.
POST aceita somente email (3–254, normalizado NFKC/minúsculas/trim),
nome (1–120 após trim) e senha (1–1024 antes da política).
Campos extras, inclusive papel e flag de troca, geram 422 VALIDACAO_FALHOU.
Cria operador ativo, sem sessão, com troca_senha_pendente=true.
Responde 201 com id, email, nome, papel, ativo, ultimo_login_em e criado_em.
GET responde 200 com array desses campos em ordem de email, sem paginação.
Nunca retorna senha nem hash. Cache-Control: no-store.
Cada gerente pode criar até 20 contas por hora, configurável por CONTAS_POR_HORA.
O limite é por gerente, retorna 429 LIMITE_CONTAS e inclui Retry-After.

Novos códigos: ACESSO_NEGADO (403), EMAIL_JA_CADASTRADO (409) e
TROCA_DE_SENHA_OBRIGATORIA (403). Reutiliza SENHA_FRACA (422),
VALIDACAO_FALHOU (422), NAO_AUTENTICADO (401) e CSRF_INVALIDO (403).
Colisões de email por caixa ou Unicode também geram EMAIL_JA_CADASTRADO;
é aceitável revelar existência ao gerente autorizado a listar contas.
Nenhuma outra operação de gestão de conta é exposta pela API.

Login e GET /api/auth/me acrescentam papel e troca_senha_pendente ao objeto
usuario. A flag pendente restringe globalmente as rotas sob /api a
GET /api/auth/me, POST /api/auth/senha e POST /api/auth/logout.
Demais rotas autenticadas geram TROCA_DE_SENHA_OBRIGATORIA; OPTIONS mantém
CORS e login continua público. A troca válida limpa a flag e revoga
sessões anteriores, emitindo novo cookie/CSRF.

---

# 4. Armadilhas

## 4.0 `GET /api/modelos-armadilha`

Catálogo dos modelos de armadilha fabricados e pré-cadastrados, usado na
escolha do modelo ao cadastrar uma armadilha. Exige sessão, como todo
endpoint sob `/api`. É somente leitura: novos modelos entram por migração.

**Resposta `200`:** apenas modelos ativos, ordenados por nome.

```json
[
  {
    "id": "b81c...",
    "codigo": "stickfly-k45",
    "nome": "StickFly K-45",
    "fabricante": "StickFly",
    "descricao": "Armadilha de parede com 3 lâmpadas UVA de 15 W...",
    "atracao": "UV-A",
    "refil_largura_mm": 450,
    "refil_altura_mm": 220
  }
]
```

## 4.1 `GET /api/armadilhas`

Lista as armadilhas com estado atual consolidado. Alimenta o dashboard.

O backend calcula `percentual_atual`, `status` e `dias_ate_saturar` — o
frontend não faz esse cálculo, conforme `../frontend/telas_spec.md`, seção 5.

**Resposta `200`:**

```json
[
  {
    "id": "3f2a...",
    "identificador": "ARM-001",
    "localizacao": "Área de recebimento",
    "modelo": "StickFly K-45",
    "modelo_id": "b81c...",
    "refil_ativo": {
      "id": "9c1b...",
      "data_instalacao": "2026-08-01",
      "dias_em_uso": 20
    },
    "percentual_atual": 64.30,
    "status": "atencao",
    "dias_ate_saturar": 4,
    "limiar_trocar": 20,
    "foto_tipo": "padrao",
    "foto_url": null,
    "ultima_analise_em": "2026-08-21T09:12:00Z",
    "em_alerta_desde": null
  }
]
```

**Ordenação:** `trocar` primeiro, depois por `dias_ate_saturar` crescente.

**Campos nulos possíveis:**

| Campo | Quando é nulo |
|---|---|
| `refil_ativo` | Armadilha sem refil ativo |
| `percentual_atual`, `status`, `ultima_analise_em` | Nenhuma análise no refil ativo |
| `dias_ate_saturar` | Menos de duas análises, ou inclinação não positiva |
| `em_alerta_desde` | Armadilha não está em estado `trocar` |

**Sobre `dias_em_uso`:** diferença entre a data de hoje e a data de instalação
do refil, em dias inteiros. "Hoje" é a data civil no fuso `FUSO_PRODUTO`
(padrão Brasília), não a data UTC: um refil instalado hoje tem 0 dia de uso
mesmo depois das 21h locais. A mesma data valida a instalação, que não pode
ser posterior a hoje. Os instantes continuam em UTC.

**Sobre `limiar_trocar`:** percentual de cobertura a partir do qual a armadilha
passa a `trocar`, igual ao `LIMIAR_TROCAR` configurado no backend. Também vem
no detalhe (4.3). O frontend o usa no texto e na linha de referência do
gráfico, em vez de repetir o valor. Nunca é nulo.

**Sobre `em_alerta_desde`:** data da primeira análise do refil ativo cujo
percentual cruzou o limiar de troca. Alimenta o painel de alertas descrito em
`../frontend/telas_spec.md`, seção 6.

O alerta não é uma entidade persistida — é derivado das análises existentes.
Este campo evita que o frontend precise buscar todo o histórico apenas para
descobrir há quanto tempo a armadilha exige ação.

## 4.2 `POST /api/armadilhas`

**Requisição:**

```json
{
  "identificador": "ARM-002",
  "modelo_id": "b81c...",
  "localizacao": "Depósito",
  "data_instalacao": "2026-08-21",
  "criar_refil_inicial": true
}
```

O campo `criar_refil_inicial` cria o primeiro refil junto com a armadilha.
Existe porque uma armadilha sem refil ativo não aceita análises, e exigir duas
chamadas separadas para o caso comum seria uma armadilha de usabilidade.

O campo `modelo_id` é opcional e deve ser o identificador de um modelo ativo
do catálogo (seção 4.0). Um identificador inexistente ou de modelo
desativado devolve `422 VALIDACAO_FALHOU`, com `detalhes.campo` igual a
`modelo_id`. O servidor grava o nome do modelo junto à armadilha; o
cliente não envia o nome.

**Resposta `201`:** objeto da armadilha criada.

## 4.3 `GET /api/armadilhas/{id}`

Detalhe de uma armadilha, incluindo refil ativo e histórico de refis
anteriores.

**Resposta `200`:**

```json
{
  "id": "3f2a...",
  "identificador": "ARM-001",
  "modelo": "StickFly K-45",
  "modelo_id": "b81c...",
  "localizacao": "Área de recebimento",
  "data_instalacao": "2026-06-15",
  "refil_ativo": {
    "id": "9c1b...",
    "data_instalacao": "2026-08-01",
    "dias_em_uso": 20
  },
  "refis_anteriores": [
    {
      "id": "7d4e...",
      "data_instalacao": "2026-06-15",
      "data_troca": "2026-07-31",
      "dias_ate_troca": 46
    }
  ],
  "percentual_atual": 64.30,
  "status": "atencao",
  "dias_ate_saturar": 4,
  "limiar_trocar": 20,
  "foto_tipo": "real",
  "foto_url": "/api/armadilhas/3f2a.../foto?v=1793323816151"
}
```

O campo `dias_ate_troca` nos refis anteriores é o dado que valida a proposta
do projeto: mostra, com histórico real, quanto tempo cada refil durou.

## 4.4 `PATCH /api/armadilhas/{id}`

Atualização parcial. Aceita `identificador`, `modelo_id` e `localizacao`.

`modelo_id` segue a regra da seção 4.2; enviar `null` desvincula o modelo.

`data_instalacao` não é editável — alterá-la invalidaria o histórico.

## 4.5 `DELETE /api/armadilhas/{id}`

Remove a armadilha do painel por **remoção lógica**: grava `removida_em` e
preserva refis, análises e imagens, que sustentam o histórico. Uma armadilha
removida deixa de aparecer na listagem e não aceita novas operações
(edição, troca de refil, análise), e o identificador continua reservado.

**Resposta `204`:** sem corpo. **Erros:** `404 ARMADILHA_NAO_ENCONTRADA` se
a armadilha não existir ou já tiver sido removida.

## 4.6 Foto de identificação

A armadilha mostra sempre uma foto: a **foto padrão do modelo**, que é um
recurso estático do frontend, ou uma **foto real** enviada por quem cadastra.
A listagem (4.1) e o detalhe (4.3) trazem dois campos:

| Campo | Valores |
|---|---|
| `foto_tipo` | `padrao` ou `real` |
| `foto_url` | Caminho relativo com `?v=<instante>` quando o tipo é `real`; nulo quando é `padrao`. O parâmetro muda a cada envio e invalida o cache |

**`PUT /api/armadilhas/{id}/foto`** — `multipart/form-data` com o campo
`arquivo`. Exige sessão e CSRF; gerente e operador podem usar. Aplica as
validações do upload de análise (seção 2.4): conteúdo real JPEG ou PNG, 4 MB,
20 milhões de pixels e 512 px de resolução mínima, com os mesmos códigos de
erro. O servidor reduz a imagem a no máximo 800 px no maior lado, converte para
JPEG (qualidade 85) e **descarta os metadados EXIF**, que podem conter a
localização; só a cópia reduzida é guardada.

**Resposta `200`:** `{ "foto_tipo": "real", "foto_url": "/api/armadilhas/{id}/foto?v=..." }`.
**Erros:** `400` arquivo ausente, formato inválido ou resolução insuficiente;
`413` acima do limite (com `detalhes.motivo`); `404 ARMADILHA_NAO_ENCONTRADA`.

**`DELETE /api/armadilhas/{id}/foto`** — volta à foto padrão. Idempotente:
`204` mesmo quando já não há foto real; `404` se a armadilha não existir.

**`GET /api/armadilhas/{id}/foto`** — devolve o JPEG reduzido (`image/jpeg`,
`Cache-Control: private`, `ETag`, `X-Content-Type-Options: nosniff`). Exige
sessão. `404 ARMADILHA_NAO_ENCONTRADA` quando a armadilha não existe, foi
removida ou usa a foto padrão. Armadilha removida não serve nem aceita foto.

---

# 5. Refis

## 5.1 `POST /api/armadilhas/{id}/refis`

Registra a troca de refil: encerra o refil ativo com `data_troca` igual à data
informada e cria um novo refil.

**Requisição:**

```json
{ "data_instalacao": "2026-08-21" }
```

**Resposta `201`:**

```json
{
  "refil_encerrado": {
    "id": "9c1b...",
    "data_instalacao": "2026-08-01",
    "data_troca": "2026-08-21",
    "dias_ate_troca": 20
  },
  "refil_novo": {
    "id": "e8f3...",
    "data_instalacao": "2026-08-21",
    "dias_em_uso": 0
  }
}
```

A operação é atômica: encerrar o refil anterior e criar o novo ocorrem na
mesma transação. Isso garante a regra de integridade de no máximo um refil
ativo por armadilha, definida em `../data/data_model.md`, seção 6.3.

Se a armadilha não tiver refil ativo, apenas o novo é criado e
`refil_encerrado` retorna nulo.

---

# 6. Análises

## 6.1 `POST /api/analises`

Executa a inferência e persiste o resultado. É o endpoint central do sistema.

**Requisição:** `multipart/form-data`

| Campo | Tipo | Obrigatório |
|---|---|---|
| `imagem` | arquivo | Sim |
| `armadilha_id` | `uuid` | Sim |

**Fluxo do processamento:**

```text
Recebe imagem e armadilha_id
        ↓
Valida arquivo e localiza refil ativo
        ↓
Persiste a imagem em data/uploads/
        ↓
Executa pré-processamento e inferência
        ↓
Calcula percentual e deriva status
        ↓
Persiste registro de análise
        ↓
Retorna resultado
```

**Resposta `201`:**

```json
{
  "id": "b2c9...",
  "refil_id": "9c1b...",
  "armadilha_id": "3f2a...",
  "analisado_em": "2026-08-21T14:30:00Z",
  "percentual_coberto": 64.30,
  "status": "atencao",
  "modelo_versao": "v1.2.0+a3f9c2e1",
  "imagem_url": "/api/analises/b2c9.../imagem",
  "mascara_url": "/api/analises/b2c9.../mascara"
}
```

O campo `mascara_url` continua na resposta, mas a interface não o consome.

**Erros:**

| Código | Situação |
|---|---|
| `400` | Arquivo ausente ou não é imagem válida |
| `404` | `armadilha_id` inexistente |
| `409` | Armadilha sem refil ativo |
| `500` | Falha na inferência |

Em caso de falha na inferência, nenhum registro parcial é persistido — a
transação é revertida e a imagem gravada é removida. Análise sem resultado
poluiria a série temporal.

## 6.2 `GET /api/armadilhas/{id}/analises`

Histórico de análises. Alimenta o gráfico e a lista de análises da tela de detalhe.

**Parâmetros de consulta:**

| Parâmetro | Valores | Padrão | Descrição |
|---|---|---|---|
| `escopo` | `refil_ativo`, `completo` | `refil_ativo` | Extensão temporal |
| `refil_id` | `uuid` | — | Restringe a um refil específico |
| `limite` | inteiro | 100 | Número máximo de registros |

**Resposta `200`:** lista de análises em ordem cronológica crescente, no mesmo
formato da seção 6.1, acrescida de `refil_id` em cada item.

O campo `refil_id` por item permite ao frontend identificar as transições
entre refis e renderizar o gráfico corretamente no modo `completo`.

**Sobre os dois escopos:**

| Escopo | Comportamento |
|---|---|
| `refil_ativo` | Apenas o ciclo atual. Padrão, por ser o relevante ao acompanhamento operacional e à projeção de saturação |
| `completo` | Todos os refis. Produz o padrão de dente de serra que evidencia os ciclos de troca |

O padrão é `refil_ativo` porque misturar refis distorce a leitura operacional:
a curva apresentaria quedas abruptas a cada troca. O modo `completo` existe
para consultas de histórico completo (a interface atual não o consome),
onde essas quedas são justamente o que se quer mostrar.

## 6.3 `GET /api/analises/{id}`

Detalhe de uma análise. Mesmo formato da seção 6.1.

## 6.4 Imagens

| Rota | Retorno |
|---|---|
| `GET /api/analises/{id}/imagem` | Imagem original |
| `GET /api/analises/{id}/mascara` | Imagem com máscara sobreposta. A interface não a consome mais; o endpoint permanece |

Servidas como binário com `Content-Type` apropriado, não como base64 embutido
no JSON. Base64 aumenta o payload em cerca de 33% e impede o cache do
navegador — em uma tela que exibe várias miniaturas, a diferença é
perceptível.

A máscara sobreposta é gerada no momento da análise e persistida junto à
imagem original, evitando reprocessamento a cada visualização.

---

# 7. Fora de escopo

| Item | Motivo |
|---|---|
| Perfis de acesso (autorização por papel) | Fase 2. Na v1 todo usuário autenticado e ativo acessa todo o sistema (`login.md`, 4.3) |
| MFA e recuperação de senha por e-mail | Fase 2 (`login.md`, 12.3); a senha é redefinida pelo administrador por linha de comando |
| Endpoints de estabelecimento | Entidade prevista para a Fase 2 |
| Endpoint de comparação com baseline | A comparação ocorre offline, nos notebooks de avaliação |
| Paginação completa | O volume do MVP não justifica; `limite` é suficiente |
| `DELETE` de armadilha | Remover armadilha com histórico exigiria decisão sobre cascata; não é necessário na demo |

---

# 8. Pendências

Nenhuma pendência de decisão.

---

# FIM DA API
