# TELAS — Projeto Integrador

**Versão:** 1.0
**Status:** ATIVO
**Escopo:** telas da interface, conteúdo e comportamento esperado

---

# 1. Objetivo

Especificar as telas da interface de demonstração. Este documento é a origem
do contrato da API — os endpoints em `../api/api_spec.md` existem para
atender ao que estas telas exibem.

---

# 2. Audiências

A interface serve a duas audiências com necessidades distintas:

| Audiência | Precisa ver |
|---|---|
| Banca avaliadora | Que o modelo funciona e que houve rigor metodológico |
| Empresa parceira | Quais armadilhas precisam de visita, e quando |

As telas do MVP atendem ambas. A comparação entre baseline e modelo treinado
fica no relatório, não na interface — ver seção 6.

---

# 3. Telas do MVP

| Tela | Rota | Papel |
|---|---|---|
| Dashboard | `/` | Estado atual de todas as armadilhas, ordenado por urgência |
| Detalhe da armadilha | `/armadilhas/:id` | Série temporal, histórico e troca de refil |
| Nova análise | `/analises/nova` | Upload de imagem e resultado do modelo |
| Cadastro de armadilha | `/armadilhas/nova`, `/armadilhas/:id/editar` | CRUD básico |

---

# 4. Especificação por tela

## 4.1 Dashboard

**Rota:** `/`

Tela inicial. Responde à pergunta operacional: *o que precisa ser feito hoje.*

**Painel de alertas:** faixa no topo da tela com a contagem de armadilhas que
exigem ação e a lista dos casos, cada um indicando há quantos dias está em
alerta. Ver seção 6.

**Conteúdo:** lista de cards ou tabela, um por armadilha, contendo:

- identificador e localização
- percentual de cobertura atual
- status visual (`ok` verde, `atencao` âmbar, `trocar` vermelho)
- estimativa de dias até saturar
- data da última análise

**Ordenação:** por urgência — armadilhas em `trocar` primeiro, depois por
menor número de dias estimados até saturar.

**Estados de exceção:**

| Situação | Comportamento |
|---|---|
| Nenhuma armadilha cadastrada | Estado vazio com chamada para cadastrar |
| Armadilha sem refil ativo | Exibida com indicação "sem refil ativo", sem percentual |
| Armadilha com menos de duas análises | Exibida sem estimativa de dias — ver seção 5 |

## 4.2 Detalhe da armadilha

**Rota:** `/armadilhas/:id`

É onde a série temporal aparece. Esta tela é o que distingue o sistema de um
classificador de imagem isolado.

**Conteúdo:**

- dados da armadilha (identificador, modelo, localização, data de instalação)
- dados do refil ativo (data de instalação, dias em uso)
- **gráfico de evolução** do percentual ao longo do tempo
- **timelapse** sincronizado ao gráfico — ver seção 4.2.1
- lista das análises, com miniatura, data, percentual e status
- botão **Registrar troca de refil**
- link para editar a armadilha

**Comportamento do botão de troca:** encerra o refil ativo, registrando a data
de troca, e cria um novo refil com data de instalação igual à data corrente. A
partir daí a série temporal recomeça do zero.

### 4.2.1 Timelapse

Reprodução automática das imagens da armadilha em ordem cronológica, com o
gráfico acompanhando em sincronia.

**Comportamento:**

- botão de reprodução inicia a animação, que avança pelas análises em
  sequência
- a cada quadro, a área de imagem exibe a foto e a máscara daquele momento
- um marcador percorre o gráfico na posição temporal correspondente
- o percentual exibido acompanha o quadro atual
- o usuário pode arrastar o marcador manualmente para inspecionar um momento
  específico, o que pausa a reprodução

**Escopo temporal:** alternável entre dois modos.

| Modo | Exibe | Uso |
|---|---|---|
| Refil ativo *(padrão)* | Apenas o ciclo atual | Acompanhamento operacional |
| Histórico completo | Todos os refis da armadilha | Demonstração dos ciclos |

No modo de histórico completo, a curva exibe o padrão de dente de serra —
sobe conforme o refil satura, cai bruscamente na troca, e volta a subir. É a
visualização que melhor comunica o ciclo de vida da armadilha e a proposta do
projeto.

**Justificativa:** os dados necessários já existem, pois cada análise
armazena imagem e data. O custo de implementação é baixo e o ganho é
demonstrar visualmente que o modelo acompanhou a evolução real — algo que o
gráfico sozinho não evidencia, já que não mostra a imagem que originou cada
medição.

**Estados de exceção:**

| Situação | Comportamento |
|---|---|
| Menos de duas análises | Timelapse oculto; exibe apenas a imagem existente |
| Nenhuma análise | Timelapse e gráfico ocultos |

## 4.3 Nova análise

**Rota:** `/analises/nova`

Demonstra o modelo funcionando. É a tela central da apresentação à banca.

**Fluxo:**

1. usuário seleciona a armadilha
2. usuário envia a imagem
3. sistema processa e exibe o resultado

**Resultado exibido:**

- imagem original e imagem com a máscara sobreposta, lado a lado
- percentual de cobertura, com destaque visual
- status classificado
- versão do modelo utilizada

**Estados de exceção:**

| Situação | Comportamento |
|---|---|
| Armadilha sem refil ativo | Bloqueia o envio e orienta a registrar um refil |
| Arquivo não é imagem válida | Mensagem de erro antes do envio |
| Falha na inferência | Mensagem de erro, sem persistir análise parcial |

Exibir a versão do modelo não é detalhe cosmético: durante o desenvolvimento o
modelo será retreinado, e sem essa informação visível fica impossível saber se
um resultado ruim veio da versão atual ou de uma anterior.

## 4.4 Cadastro de armadilha

**Rotas:** `/armadilhas/nova` e `/armadilhas/:id/editar`

Formulário simples com: identificador, modelo, localização e data de
instalação.

Ao criar uma armadilha, o sistema deve oferecer a criação imediata do primeiro
refil — uma armadilha sem refil ativo não aceita análises, e essa dependência
não é óbvia para quem usa.

---

# 5. Estimativa de dias até saturar

O valor exibido no dashboard é calculado no backend, não no frontend — é
regra de negócio.

**Método:** regressão linear sobre **todas** as análises do refil ativo.

```text
Ajusta a reta:  percentual = a × dias + b
                sobre todos os pares (dias_desde_instalacao, percentual)

Resolve para o limiar:  dias_previstos = (LIMIAR_TROCAR − b) / a

dias_ate_saturar = dias_previstos − dias_decorridos
```

Onde `LIMIAR_TROCAR` é 70, conforme
`../foundation/project_overview.md`, seção 7.2.

## 5.1 Por que regressão e não dois pontos

A alternativa mais simples seria calcular a taxa entre a primeira e a última
análise. Foi rejeitada por ser **o método mais sensível a erro de medição**:
descarta todas as leituras intermediárias e depende inteiramente de dois
valores.

Considere uma armadilha que realmente vai de 30% para 50% em sete dias — taxa
de aproximadamente 2,9 pontos por dia, saturando em cerca de sete dias. Com
erro de medição de ±10 pontos e apenas dois pontos considerados:

| Leitura obtida | Dia 1 | Dia 8 | Projeção resultante |
|---|---|---|---|
| Desfavorável A | 40% | 40% | Não satura |
| Desfavorável B | 20% | 60% | Satura em 2 dias |

A mesma realidade produz respostas que vão de "nunca" a "depois de amanhã".

Com regressão sobre dez medições, erros individuais em direções opostas se
compensam, e a inclinação estimada é substancialmente mais estável. O custo é
uma chamada de ajuste linear.

Isso importa porque o critério de precisão do modelo, definido em
`../model/avaliacao_spec.md`, seção 4.2, foi estabelecido **em função desta
projeção**. Exigir precisão do modelo para compensar um cálculo frágil seria
transferir o problema para o lugar errado.

## 5.2 Casos em que a estimativa não é calculada

| Condição | Retorno |
|---|---|
| Menos de duas análises no refil ativo | Nulo — sem base para ajustar reta |
| Inclinação menor ou igual a zero | Nulo — armadilha não está enchendo |
| Percentual atual acima do limiar | Zero — já deve ser trocada |
| `dias_previstos` anterior à data atual | Zero — mesma situação |

Com exatamente duas análises, a regressão coincide com a reta entre os dois
pontos. O ganho aparece a partir da terceira, e cresce com o número de
medições.

## 5.3 Percentual exibido

O valor apresentado como percentual atual é sempre a **última medição real**,
nunca o valor estimado pela reta ajustada.

A regressão serve para estimar a tendência, não para corrigir a medição. Exibir
um valor calculado no lugar do medido confundiria o usuário ao comparar com a
lista de análises logo abaixo, na mesma tela.

---

# 6. Alertas

## 6.1 O que é um alerta neste contexto

No MVP a imagem é enviada manualmente — não há câmera automática, conforme
`../foundation/project_overview.md`, seção 5.2. Logo, o alerta nunca dispara
sozinho: ele surge no mesmo instante em que alguém envia a foto e já vê o
resultado.

Isso define o que o alerta é aqui: **um painel do que exige ação**, e não uma
notificação que chega ao usuário. A lista permanece visível até que a troca do
refil seja registrada.

## 6.2 Regra de derivação

O alerta **não é uma entidade persistida**. É derivado dos dados existentes:

| Informação | Origem |
|---|---|
| Alerta ativo | Última análise do refil ativo com percentual acima do limiar |
| Início do alerta | Primeira análise daquele refil que cruzou o limiar |
| Resolução do alerta | Registro da troca do refil (`refil.data_troca`) |

Uma tabela `alerta` apenas duplicaria informação já presente em `analise` e
`refil`, com risco de dessincronização. O único ganho seria registrar que
alguém visualizou ou ignorou o alerta, o que não é relevante sem usuários
autenticados — fora do escopo do MVP.

## 6.3 Apresentação

Faixa no topo do dashboard contendo:

- contagem de armadilhas em estado `trocar`
- lista dos casos, com identificador, localização e há quantos dias o alerta
  está ativo
- link direto para o detalhe de cada armadilha

Quando não há alertas, a faixa exibe confirmação de que nenhuma ação é
necessária, em vez de ser ocultada — a ausência explícita comunica mais do que
a ausência do elemento.

## 6.4 Fora de escopo

Notificação externa (e-mail, push, webhook) não entra no MVP. Faria sentido
apenas com captura automática de imagem, que está fora do escopo — sem ela,
não há evento assíncrono a notificar.

---

# 7. Fora de escopo

| Item | Motivo |
|---|---|
| Tela de comparação baseline vs. modelo | Serve à banca, não ao uso operacional. A comparação fica no relatório e nos notebooks de avaliação |
| Autenticação e múltiplos usuários | Fora do escopo do MVP conforme `project_overview.md` |
| Cadastro de estabelecimento | Entidade prevista para a Fase 2 |
| Responsividade mobile completa | A demo roda em desktop; PWA é evolução futura |

---

# 8. Decisões visuais e técnicas

## 8.1 Biblioteca de gráfico

**Recharts.** Possui `ReferenceLine`, usada como marcador móvel do timelapse,
API declarativa em React e volume de dados compatível com a escala do projeto.

## 8.2 Paleta de status

| Status | Cor | Hex |
|---|---|---|
| `ok` | Verde | `#16A34A` |
| `atencao` | Âmbar | `#F59E0B` |
| `trocar` | Vermelho | `#DC2626` |

A cor **nunca** é o único indicador — todo elemento que comunica status exibe
também o rótulo textual. Distinção apenas por cor exclui usuários com
daltonismo, e vermelho e verde são justamente o par mais afetado.

**Grafia:** a API trafega `atencao`, sem acento. O frontend exibe "Atenção". A
conversão ocorre apenas na camada de apresentação.

## 8.3 Máscara sobreposta

Gerada pelo backend e recebida pronta, conforme
`../model/modelo_spec.md`, seção 7.1 — magenta a 40% de opacidade sobre a
imagem original.

O frontend exibe original e máscara lado a lado, sem processamento próprio.

## 8.4 Timelapse

| Item | Valor |
|---|---|
| Velocidade padrão | 500 ms por quadro |
| Faixa ajustável | 200 ms a 2000 ms |
| Comportamento ao final | Para no último quadro, sem repetir |

## 8.5 Nomenclatura

O frontend mantém `snake_case` nos dados vindos da API, sem camada de
conversão para `camelCase`.

A conversão exigiria tipos duplicados — um para o formato da API, outro para o
formato interno — e uma camada de mapeamento em ambas as direções. Cada campo
novo passaria a exigir alteração em três lugares. O ganho seria apenas
aderência à convenção idiomática do TypeScript, que não compensa o custo nesta
escala.

Código próprio do frontend, sem relação com a API, segue `camelCase`
normalmente.

---

# 9. Pendências

Nenhuma pendência de decisão.

---

# FIM DAS TELAS
