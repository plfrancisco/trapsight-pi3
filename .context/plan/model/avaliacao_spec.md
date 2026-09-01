# AVALIAÇÃO DO MODELO — Projeto Integrador

**Versão:** 1.0
**Status:** ATIVO
**Escopo:** divisão dos conjuntos, métricas e critérios de aprovação

---

# 1. Objetivo

Definir como o modelo é avaliado e o que caracteriza um resultado aprovado.

Sem critério numérico definido antes do treino, qualquer resultado pode ser
justificado depois — e a decisão de concluir o MVP passa a ser subjetiva.

---

# 2. Divisão dos conjuntos

## 2.1 Conjuntos

| Conjunto | Origem | Uso |
|---|---|---|
| Treino | Sintético | Ajuste dos pesos |
| Validação | Sintético | Seleção de época e hiperparâmetros |
| Teste sintético | Sintético | Métrica final sobre o domínio de treino |
| **Teste real** | Fotos reais | Métrica final sobre o domínio de produção |

## 2.2 Proporções

O conjunto sintético é dividido em **70% treino, 15% validação, 15% teste**.

Fotos reais **não são divididas** — a totalidade é reservada para teste. Isso
vale para a Fase 1. Na Fase 2, quando houver volume suficiente para
fine-tuning, a divisão é redefinida e registrada aqui.

## 2.3 Regras de separação

| Regra | Definição |
|---|---|
| Divisão por semente de geração | Cada imagem sintética é gerada a partir de uma semente registrada; a divisão ocorre por semente, nunca por arquivo |
| Sem reuso entre conjuntos | Uma imagem de teste nunca aparece em treino, em nenhuma variação ou augmentação |
| Augmentação apenas em treino | Validação e teste usam as imagens como geradas, sem transformação adicional |
| Fotos reais isoladas | Nunca entram em treino na Fase 1, sob nenhuma circunstância |

A divisão por semente evita um vazamento sutil: se a divisão fosse por
arquivo, duas augmentações da mesma imagem base poderiam cair em conjuntos
diferentes. O modelo veria em teste uma variação do que treinou, e a métrica
ficaria otimista sem que nada indicasse o problema.

## 2.4 Registro obrigatório

Conforme `../../rules/ai_development_rules.md`, seção 9.1, cada execução de
treino registra:

- semente global
- sementes usadas na geração de cada conjunto
- hiperparâmetros
- versões das bibliotecas relevantes
- `modelo_versao` resultante

---

# 3. Métricas

## 3.1 Métricas de segmentação

| Métrica | O que mede |
|---|---|
| Dice | Sobreposição entre máscara predita e gabarito |
| IoU | Sobreposição, com penalização mais severa que o Dice |

Calculadas por classe e como média. A classe `placa_coberta` é a
determinante; `fundo` e `placa_limpa` servem para diagnosticar falhas de
detecção da placa.

## 3.2 Métrica de negócio

**Erro absoluto do percentual**, em pontos percentuais:

```text
erro = | percentual_predito − percentual_real |
```

Esta é a métrica que importa para o produto. Dice e IoU medem qualidade
pixel a pixel; o erro percentual mede o que o sistema efetivamente informa ao
usuário.

As duas podem divergir: erros de segmentação em direções opostas se cancelam
no agregado, produzindo percentual correto com Dice medíocre. Por isso ambas
são reportadas — a segunda valida a primeira.

## 3.3 Métricas de classificação

- Acurácia do status sobre o conjunto de teste
- Matriz de confusão entre `ok`, `atencao` e `trocar`

---

# 4. Critérios de aprovação

## 4.1 Limiares

| Métrica | Alvo | Mínimo aceitável |
|---|---|---|
| Erro percentual — teste sintético | ≤ 3 pp | ≤ 5 pp |
| Erro percentual — teste real | ≤ 5 pp | ≤ 10 pp |
| Dice `placa_coberta` — teste sintético | ≥ 0,90 | ≥ 0,85 |
| Dice `placa_coberta` — teste real | ≥ 0,80 | ≥ 0,75 |
| Acurácia do status — teste real | ≥ 90% | ≥ 85% |
| Casos `trocar` classificados como `ok` | 0 | 0 |

## 4.2 Origem do alvo de 5 pontos percentuais

O limite não decorre de convenção de aprendizado de máquina, e sim do
consumidor mais exigente do resultado: a projeção de dias até saturar,
definida em `../frontend/telas_spec.md`, seção 5.

A projeção estima a taxa de saturação por regressão linear sobre as medições
do refil ativo. Com ruído de ±10 pp, duas leituras de 30% e 50% separadas por
sete dias — taxa real de 2,9 pp por dia — poderiam corresponder a uma taxa
nula ou ao dobro da real. A projeção perderia qualquer utilidade.

Com ±5 pp, a incerteza da inclinação permanece dentro de margem aceitável para
uma estimativa em dias.

A regressão sobre múltiplos pontos, e não sobre apenas o primeiro e o último,
é parte da mitigação: erros individuais em direções opostas se compensam. As
duas medidas atuam em conjunto — precisão do modelo e robustez do cálculo — e
nenhuma delas isoladamente seria suficiente.

## 4.3 Erro crítico

`trocar` classificado como `ok` é um salto de duas faixas na direção perigosa:
a armadilha está saturada e o sistema informa que está em ordem.

Um único caso reprova a avaliação, independentemente das demais métricas. Não
há tolerância percentual para este erro.

O caso inverso — `ok` classificado como `trocar` — é contabilizado na acurácia
mas não é crítico: gera troca antecipada, com custo material, não falha
funcional.

## 4.4 Interpretação da diferença entre sintético e real

A distância entre as duas colunas da tabela 4.1 **é a medida do domain gap**.

| Situação | Interpretação |
|---|---|
| Ambos dentro do alvo | Modelo aprovado |
| Sintético bom, real ruim | O modelo aprendeu, mas o dataset sintético não representa a realidade. O problema está no gerador, não na rede |
| Ambos ruins | Problema de arquitetura, treino ou volume de dados |
| Real melhor que sintético | Indício de erro na avaliação ou vazamento entre conjuntos |

Essa distinção é o que transforma um resultado ruim em diagnóstico acionável,
e constitui uma seção relevante do relatório final.

---

# 5. Comparação com o baseline

Toda avaliação reporta modelo e baseline OpenCV lado a lado, nas mesmas
imagens de teste, conforme `../foundation/tech_stack.md`, seção 4.2.

**Condições adicionais obrigatórias:** a comparação inclui subconjuntos
específicos, porque em imagens limpas e bem iluminadas o baseline tende a
apresentar desempenho próximo ao do modelo — o que não sustentaria a escolha
técnica.

| Subconjunto | O que evidencia |
|---|---|
| Variação acentuada de iluminação e ângulo | Sombras na moldura contadas como área coberta pelo baseline |
| **Refis com sujeira acumulada** | Superestimação do baseline, que não distingue sujeira de inseto |
| **Refis amarelados, por idade** | Perda de validade do limiar fixo conforme o contraste diminui |

Os dois últimos são os mais relevantes, e ambos apontam na mesma direção.

Conforme `modelo_spec.md`, seção 3, sujeira não conta como área coberta — e um
limiar de brilho não tem como fazer essa distinção. Conforme a seção 4.2.1 do
mesmo documento, a placa escurece com o amarelamento, o que reduz o contraste
e degrada qualquer limiar calibrado em refis novos.

**Os dois erros são cumulativos e crescem com o tempo de exposição** —
justamente quando a decisão de troca se torna crítica.

## 5.1 Análise por idade do refil

A comparação deve reportar o erro de ambos os métodos **em função da idade do
refil**, não apenas como média agregada.

Uma média única esconderia o padrão mais informativo do trabalho: espera-se que
baseline e modelo tenham desempenho próximo em refis novos e divirjam
progressivamente conforme o refil envelhece.

Esse gráfico — erro versus idade, duas curvas — é o resultado que sustenta a
escolha técnica com evidência. O argumento deixa de ser "o modelo é melhor" e
passa a ser "o método clássico falha exatamente na condição em que a decisão
importa".

---

# 6. Momento da avaliação

| Momento | Conjunto | Finalidade |
|---|---|---|
| Durante o treino, por época | Validação | Seleção da melhor época |
| Ao final do treino | Teste sintético | Métrica do domínio de treino |
| Ao final do treino | Teste real | Métrica do domínio de produção |

O conjunto de teste **não é consultado durante o desenvolvimento**. Ajustar
hiperparâmetros observando o teste transforma-o em conjunto de validação, e a
métrica final deixa de estimar generalização.

---

# 7. Pendências

- [ ] Definir volume mínimo de fotos reais para que o teste real seja
      estatisticamente relevante
- [ ] Definir critério de anotação para casos ambíguos entre inseto e
      sujeira — fragmentos, insetos parcialmente degradados e aglomerados
      com poeira aderida

---

# FIM DA AVALIAÇÃO DO MODELO
