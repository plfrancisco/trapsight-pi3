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
| `404` | Recurso não encontrado |
| `409` | Conflito de estado — ex.: análise em armadilha sem refil ativo |
| `413` | Arquivo acima do limite de tamanho |
| `422` | Falha de validação de campo |
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
| `ARQUIVO_MUITO_GRANDE` | 413 | Acima de 10 MB |
| `VALIDACAO_FALHOU` | 422 | Campo obrigatório ausente ou inválido |
| `PLACA_NAO_DETECTADA` | 500 | Modelo não localizou a superfície adesiva |
| `FALHA_INFERENCIA` | 500 | Erro durante a execução do modelo |
| `REQUISICAO_INVALIDA` | 400 | Requisição rejeitada pelo framework antes de chegar à rota (ex.: corpo multipart malformado) |
| `ROTA_NAO_ENCONTRADA` | 404 | Rota inexistente |
| `METODO_NAO_PERMITIDO` | 405 | Método HTTP não aceito pela rota |
| `ERRO_INTERNO` | 500 | Falha inesperada; a mensagem é genérica e o detalhe fica só no log do servidor |

## 2.4 Restrições de upload

| Restrição | Valor |
|---|---|
| Tamanho máximo | 10 MB |
| Formatos aceitos | JPEG, PNG |
| Resolução mínima | 512 px no maior lado |
| Resolução máxima | 20 milhões de pixels decodificados — protege contra *decompression bomb*; acima disso a resposta é `413` `ARQUIVO_MUITO_GRANDE`. Dentro do limite, a imagem é redimensionada no pré-processamento |

O mínimo de 512 px decorre da resolução de entrada do modelo, definida em
`../model/modelo_spec.md`, seção 6. Imagens menores seriam ampliadas, sem
ganho real de informação e com perda de precisão na segmentação.

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
— porta padrão do Vite.

**Variáveis de ambiente do backend:**

| Variável | Exemplo | Obrigatória |
|---|---|---|
| `DATABASE_URL` | `postgresql://user:senha@db:5432/armadilhas` | Sim |
| `MODEL_WEIGHTS_PATH` | `/app/models/checkpoints/latest.pt` | Sim |
| `MODEL_VERSION` | `v0.1.0-dev` | Sim |
| `UPLOADS_DIR` | `/app/data/uploads` | Sim |
| `CORS_ORIGENS` | `http://localhost:5173` | Sim |
| `LIMIAR_ATENCAO` | `40` | Não — padrão 40 |
| `LIMIAR_TROCAR` | `70` | Não — padrão 70 |

**Variáveis do frontend:**

| Variável | Exemplo |
|---|---|
| `VITE_API_URL` | `http://localhost:8000/api` |

Os limiares são variáveis de ambiente porque serão recalibrados com dados
reais, conforme `../foundation/project_overview.md`, seção 7.2. Fixá-los no
código exigiria alteração e novo build a cada ajuste.

---

# 3. Mapa de endpoints

| Método | Rota | Tela que atende |
|---|---|---|
| `GET` | `/api/armadilhas` | Dashboard |
| `POST` | `/api/armadilhas` | Cadastro |
| `GET` | `/api/armadilhas/{id}` | Detalhe |
| `PATCH` | `/api/armadilhas/{id}` | Cadastro (edição) |
| `POST` | `/api/armadilhas/{id}/refis` | Detalhe (troca de refil) |
| `GET` | `/api/armadilhas/{id}/analises` | Detalhe (gráfico e histórico) |
| `POST` | `/api/analises` | Nova análise |
| `GET` | `/api/analises/{id}` | Nova análise (resultado) |

---

# 4. Armadilhas

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
    "refil_ativo": {
      "id": "9c1b...",
      "data_instalacao": "2026-08-01",
      "dias_em_uso": 20
    },
    "percentual_atual": 64.30,
    "status": "atencao",
    "dias_ate_saturar": 4,
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
  "modelo": "StickFly K-45",
  "localizacao": "Depósito",
  "data_instalacao": "2026-08-21",
  "criar_refil_inicial": true
}
```

O campo `criar_refil_inicial` cria o primeiro refil junto com a armadilha.
Existe porque uma armadilha sem refil ativo não aceita análises, e exigir duas
chamadas separadas para o caso comum seria uma armadilha de usabilidade.

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
  "dias_ate_saturar": 4
}
```

O campo `dias_ate_troca` nos refis anteriores é o dado que valida a proposta
do projeto: mostra, com histórico real, quanto tempo cada refil durou.

## 4.4 `PATCH /api/armadilhas/{id}`

Atualização parcial. Aceita `identificador`, `modelo` e `localizacao`.

`data_instalacao` não é editável — alterá-la invalidaria o histórico.

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

Histórico de análises. Alimenta o gráfico e o timelapse da tela de detalhe.

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
para o timelapse de demonstração, onde essas quedas são justamente o que se
quer mostrar.

## 6.3 `GET /api/analises/{id}`

Detalhe de uma análise. Mesmo formato da seção 6.1.

## 6.4 Imagens

| Rota | Retorno |
|---|---|
| `GET /api/analises/{id}/imagem` | Imagem original |
| `GET /api/analises/{id}/mascara` | Imagem com máscara sobreposta |

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
| Autenticação e autorização | Fora do escopo do MVP |
| Endpoints de estabelecimento | Entidade prevista para a Fase 2 |
| Endpoint de comparação com baseline | A comparação ocorre offline, nos notebooks de avaliação |
| Paginação completa | O volume do MVP não justifica; `limite` é suficiente |
| `DELETE` de armadilha | Remover armadilha com histórico exigiria decisão sobre cascata; não é necessário na demo |

---

# 8. Pendências

Nenhuma pendência de decisão.

---

# FIM DA API
