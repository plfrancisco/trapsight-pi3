# PIPELINE DE TREINO — Projeto Integrador

**Versão:** 1.0
**Status:** ATIVO
**Escopo:** entrada, função de perda, otimização, augmentation, seleção de
modelo, reprodutibilidade e experimentos do treino da U-Net

---

# 1. Objetivo

Especificar de forma fechada como a U-Net é treinada, de modo que a ML04 possa
ser implementada sem decisões de projeto em aberto, e que cada valor escolhido
tenha origem declarada.

Este documento complementa `modelo_spec.md` (o que o modelo faz) e
`avaliacao_spec.md` (como é julgado). Não altera nenhum dos dois.

## 1.1 Como ler os valores

Cada decisão carrega uma origem:

| Origem | Significado |
|---|---|
| **Spec** | Decorre de outro documento normativo; não muda sem alterá-lo |
| **Prática** | Valor padrão consolidado para o tipo de problema |
| **Hipótese** | Ponto de partida razoável, **ajustado pela validação** (seção 11) |

Valores marcados como hipótese não são fixados à mão: são o primeiro ponto de
uma busca registrada, e o resultado da validação os substitui.

---

# 2. Modelo e dados de entrada

| Item | Definição | Origem |
|---|---|---|
| Arquitetura | `segmentation_models_pytorch`, U-Net, encoder `resnet34` | Spec (`tech_stack.md`, seção 4) |
| Pesos iniciais do encoder | ImageNet | Spec |
| Canais de saída | 3 (`fundo`, `placa_limpa`, `placa_coberta`) | Spec (`modelo_spec.md`, seção 2) |
| Resolução | 768 × 576 | Spec (`modelo_spec.md`, seção 6) |
| Normalização | Média e desvio-padrão do ImageNet | Spec |
| Máscara | Mapa de rótulos `uint8` com valores 0, 1 e 2 | Spec |

O dataset é gerado já em 768 × 576 (`--largura 768 --altura 576`), de modo que
o treino não redimensiona imagens. Qualquer redimensionamento aplicado a uma
imagem é aplicado à máscara com interpolação por vizinho mais próximo, nunca
bilinear: interpolar rótulos cria classes inexistentes.

## 2.1 Treino não usa cor absoluta

`modelo_spec.md`, seção 4.1: a cor da placa é imprevisível. O treino não pode
introduzir um atalho por cor. Isso se traduz em duas regras:

- a variação de cor da augmentation é **independente** do percentual de
  cobertura e da idade simulada (seção 5.3);
- a verificação de atalho da seção 10.3 é obrigatória antes de aprovar.

## 2.2 Memória de vídeo (RTX 3050, 6 GB)

U-Net com ResNet34 em 768 × 576 usa muita memória de ativação. Estratégia,
nesta ordem:

| Medida | Definição | Origem |
|---|---|---|
| Precisão mista | `torch.autocast` em fp16 com `GradScaler` | Prática |
| Formato de memória | `channels_last` | Prática |
| Tamanho de lote por passo | Maior valor de {8, 6, 4, 2} que caiba com folga de 10% de VRAM, descoberto por teste automático antes do treino | Hipótese |
| Lote efetivo | 8, por acúmulo de gradiente quando o lote por passo for menor | Hipótese |
| Carregamento | `num_workers` ≤ núcleos físicos − 1, `pin_memory=True`, persistente | Prática |

O lote por passo escolhido é registrado na execução (seção 9). O lote efetivo é
o que define a dinâmica do treino; o lote por passo é só uma restrição de
hardware.

## 2.3 Camadas de normalização com lote pequeno

Com lote por passo de 2 a 4, as estatísticas de `BatchNorm` ficam ruidosas. O
encoder mantém as camadas `BatchNorm` em modo de avaliação (estatísticas do
ImageNet congeladas) durante **todo** o treino; os pesos continuam treináveis.
O decoder usa `BatchNorm` normal. Origem: prática; confirmado ou descartado no
experimento E2 da seção 11.

---

# 3. Função de perda

## 3.1 O problema

Numa placa com 10% de cobertura, `placa_coberta` ocupa uma minoria dos pixels
de área útil. Um modelo que prevê `placa_limpa` em toda a placa teria alta
acurácia de pixel e erro percentual de 10 pontos — falha total para o produto.
Uma `CrossEntropy` simples, sem tratamento, converge para esse comportamento.

O problema agrava-se por uma segunda razão: o gerador estratifica o dataset em
terços de cobertura, então a média de cobertura é alta (~50%), mas as imagens
da faixa `ok` ainda contêm poucos pixels de classe positiva, e é nelas que o
erro de poucos pontos percentuais importa mais.

## 3.2 Definição

```text
L = L_ce  +  L_dice  +  λ · L_area
```

| Termo | Definição | Origem |
|---|---|---|
| `L_ce` | Entropia cruzada com pesos por classe | Prática |
| `L_dice` | `1 − Dice` por classe sobre as probabilidades `softmax`, com média ponderada entre classes. Implementação própria, porque `smp.losses.DiceLoss` não aceita pesos por classe | Prática |
| `L_area` | `| p̂ − p |`, em fração, onde `p̂` é o percentual derivado das probabilidades suaves (seção 3.4) e `p` o percentual real da máscara | Hipótese |
| `λ` | 0 na primeira execução; 0,5 no experimento E4 | Hipótese |

## 3.3 Pesos de classe

Pesos de `L_ce` calculados **uma vez**, sobre as máscaras do conjunto de
treino (nunca validação ou teste), por frequência de pixels `f_c`:

```text
w_c = (f_máx / f_c) ^ 0,5       # a classe mais frequente tem peso 1
w_c = min(w_c, 10)               # limite superior
```

A raiz suaviza o peso: o inverso direto da frequência dá peso excessivo a uma
classe rara e desestabiliza o treino. O teto só atua quando a razão entre a
classe mais frequente e a mais rara passa de 100 para 1; normalizar os pesos
para média 1, como numa primeira redação, limitaria qualquer peso a 3 com três
classes e tornaria o teto inócuo. Só as razões importam, porque a entropia
cruzada e o Dice dividem pela soma dos pesos. Os pesos calculados são gravados
na execução. O mesmo vetor é usado como peso das classes em `L_dice`, com
`placa_coberta` recebendo no mínimo o maior peso entre as três.

Origem: prática, com o expoente (0,5) e o teto (10) como hipóteses ajustadas
em E3.

## 3.4 Termo de área (`L_area`)

Dice e IoU medem a sobreposição pixel a pixel; o produto informa um
**percentual**. Erros de segmentação em direções opostas se cancelam no
agregado (`avaliacao_spec.md`, seção 3.2): Dice medíocre com percentual
correto, ou o contrário. Treinar diretamente contra o percentual alinha a
otimização com a métrica de negócio.

```text
área_placa_suave   = Σ (P_limpa + P_coberta)
área_coberta_suave = Σ P_coberta
p̂ = área_coberta_suave / área_placa_suave
```

onde `P_*` são as probabilidades `softmax`. O denominador usa a área da placa
prevista, igual a `modelo_spec.md`, seção 5. O termo é diferenciável. É
calculado por imagem e depois tira-se a média sobre o lote.

Fica desligado (`λ = 0`) na primeira execução para que o resultado de `L_ce +
L_dice` sirva de referência; o experimento E4 mede se ligá-lo reduz o erro
percentual sem degradar o Dice.

---

# 4. Otimização

| Item | Definição | Origem |
|---|---|---|
| Otimizador | AdamW | Prática |
| Taxa de aprendizado do decoder | 3e-4 | Hipótese |
| Taxa de aprendizado do encoder | 1e-4 | Hipótese |
| Decaimento de pesos | 1e-4 | Hipótese |
| Agendamento | Aquecimento linear de 2 épocas, depois decaimento por cosseno até 1e-6 | Prática |
| Épocas máximas | 60 | Hipótese |
| Corte de gradiente | Norma máxima 1,0 | Prática |

A taxa menor no encoder preserva o que o pré-treino ImageNet já aprendeu
(bordas, texturas) e deixa o decoder, inicializado ao acaso, adaptar-se mais
rápido.

## 4.1 Congelamento inicial do encoder

Nas **3 primeiras épocas** os pesos do encoder ficam congelados; depois são
liberados. Evita que gradientes enormes do decoder recém-inicializado destruam
as características pré-treinadas. Origem: prática; o experimento E1 mede o
ganho do pré-treino com e sem congelamento.

## 4.2 Parada antecipada

| Item | Definição | Origem |
|---|---|---|
| Frequência de avaliação | Toda época, no conjunto de validação | Spec (`avaliacao_spec.md`, seção 6) |
| Paciência | 10 épocas sem melhora do critério da seção 4.3 | Hipótese |
| Melhora mínima | 0,05 ponto percentual no critério | Hipótese |

## 4.3 Critério de seleção do melhor ponto

A seleção usa **apenas a validação**. Ordem de decisão:

1. menor número de casos `trocar` classificados como `ok` na validação
   (erro crítico, `avaliacao_spec.md`, seção 4.3);
2. entre os empatados, menor erro percentual absoluto médio na validação;
3. persistindo o empate, maior Dice de `placa_coberta`.

O erro percentual vem antes do Dice porque é a métrica que o produto informa
(`avaliacao_spec.md`, seção 3.2). O Dice entra como critério de desempate e
como diagnóstico. O melhor ponto segundo o Dice também é salvo, por
comparação.

---

# 5. Augmentation

Aplicada **somente ao conjunto de treino** (`avaliacao_spec.md`, seção 2.3),
com `Albumentations`, a imagem e a máscara juntas.

## 5.1 Fotométrica (só imagem)

| Transformação | Faixa | Condição que cobre |
|---|---|---|
| Deslocamento de matiz e saturação | matiz ±25°, saturação ±30% | Dominante violeta, balanço de branco automático |
| Ganho independente por canal RGB | 0,75–1,25 | Balanço de brancos variável |
| Brilho e contraste | ±25% | Luz ambiente concorrente |
| Gradiente de iluminação linear | até 30% de variação | Lâmpadas pontuais |
| Reflexo especular | 0–2 manchas gaussianas saturadas, raio 3–8% da largura | Lâmpadas próximas, buracos aparentes |
| Sombra de moldura | Faixa escurecida nas bordas, até 35% | Geometria da armadilha |
| Desfoque gaussiano | σ até 1,5 px | Foco |
| Ruído gaussiano | desvio até 0,03 | Sensor |
| Compressão JPEG | qualidade 60–100 | Fotos reais comprimidas |

## 5.2 Geométrica (imagem e máscara)

| Transformação | Faixa | Observação |
|---|---|---|
| Espelhamento horizontal e vertical | 50% cada | A armadilha é simétrica para o modelo |
| Rotação | ±10° | Ângulo de instalação e de captura |
| Escala | 0,9–1,1 | Distância da câmera |
| Translação | ±5% | Enquadramento |
| Perspectiva leve | escala até 0,03 | Ângulo de captura |

## 5.3 O que é proibido

| Proibição | Motivo |
|---|---|
| `MixUp`, `CutMix`, `Cutout` e recortes aleatórios que cortem a placa | Alteram a razão entre áreas, que é exatamente o que o modelo mede |
| Interpolação não-vizinho na máscara | Cria rótulos inexistentes |
| Variação de cor correlacionada ao percentual ou à idade | Cria o atalho descrito em `modelo_spec.md`, seção 4.2.2 |
| Distorção anisotrópica forte (proporção fora de 0,9–1,1) | Altera numerador e denominador de forma desigual |
| Aplicar augmentation em validação ou teste | `avaliacao_spec.md`, seção 2.3 |

A variação fotométrica é amostrada **independentemente** de qualquer metadado
da amostra. Isso preserva a independência estatística entre tom da placa e
cobertura que o gerador estabeleceu (`dataset_sintetico.md`, seção 4.3).

## 5.4 Robustez não é augmentation

Os subconjuntos de **teste de robustez** (iluminação e ângulo extremos,
sujeira acumulada, idade) são gerados à parte, com sementes disjuntas das de
treino, e medem o modelo e o baseline. Nunca entram no treino. A geração desses
subconjuntos é tarefa da ML06; este documento só fixa que eles pertencem ao
conjunto de teste e que o treino não os vê.

---

# 6. Divisão dos conjuntos

| Item | Definição | Origem |
|---|---|---|
| Proporção | 70% treino, 15% validação, 15% teste | Spec (`avaliacao_spec.md`, seção 2.2) |
| Critério | Por **semente de geração**, nunca por arquivo | Spec |
| Fonte da divisão | Campo `conjunto` do `metadados.jsonl` (`treino`, `validacao`, `teste`) | Spec |
| Estratificação | Por faixa de cobertura (`ok`, `atencao`, `trocar`) e por faixa de idade | Prática |
| Volume inicial | 3.000 imagens (2.100 / 450 / 450) | Spec (`dataset_sintetico.md`, seção 7.2) |

## 6.1 Verificações automáticas antes de treinar

O treino recusa começar se qualquer verificação falhar:

1. nenhuma semente aparece em mais de um conjunto;
2. nenhum identificador aparece em mais de um conjunto;
3. cada conjunto tem as três faixas de cobertura, em proporção próxima de 1/3;
4. o percentual recalculado de cada máscara coincide com
   `percentual_cobertura_real` (tolerância de 0,01 pp);
5. a correlação de Pearson entre `idade_simulada_dias` e
   `percentual_cobertura_real` no treino tem módulo menor que 0,1.

## 6.2 O teste é lido uma única vez

O conjunto de teste não é consultado durante o desenvolvimento
(`avaliacao_spec.md`, seção 6). A avaliação final grava um arquivo de
resultado com o hash do checkpoint, o hash do `metadados.jsonl` e a data.
Reavaliar o teste com outro checkpoint cria um novo arquivo, e o histórico
fica visível. Ajustar hiperparâmetros observando o teste o transformaria em
validação.

---

# 7. Pesos por grupo de inseto

O gerador compõe cada imagem com pesos por grupo (padrão de 70% de voadores:
mosca, mosquito e mariposa; 30% de rasteiros: formiga, barata e besouro) e os
registra em `pesos_grupo`. O treino **não reponderiza** amostras por grupo: a
composição já é decisão do gerador, alinhada ao equipamento de referência
(armadilha UV de voadores).

Na avaliação, o erro é analisado por composição de grupo (por exemplo, por
faixa de proporção de voadores). Uma análise por **área coberta por grupo**
exige que o gerador registre a fração de área de cada grupo por imagem; isso
é uma pendência do gerador (seção 12), não do treino.

---

# 8. Experimentos

Ordem fixa. Cada experimento muda **uma** variável em relação ao anterior, e
todos usam a mesma semente global, o mesmo dataset e a mesma divisão.

| ID | Pergunta | Variável | Decisão que resolve |
|---|---|---|---|
| E0 | O pipeline funciona de ponta a ponta? | 1.000 imagens, 5 épocas | Teste de fumaça; **não** é resultado |
| E1 | O pré-treino ImageNet ajuda? | encoder pré-treinado vs. inicialização aleatória | Mantém ou descarta o pré-treino |
| E2 | Congelar `BatchNorm` do encoder é melhor? | estatísticas congeladas vs. normais | Seção 2.3 |
| E3 | Os pesos de classe são adequados? | expoente 0,5 vs. 1,0 e teto 10 vs. 5 | Seção 3.3 |
| E4 | O termo de área reduz o erro percentual? | `λ` 0 vs. 0,5 | Seção 3.4 |
| E5 | O volume basta? | 25%, 50% e 100% do treino | Curva de aprendizado; decide ampliar o dataset |
| E6 (opcional) | Outra arquitetura compensa? | U-Net vs. FPN, mesmo encoder | Apoia o relatório (`tech_stack.md`, seção 4.1) |

Orçamento: no máximo **8 treinos completos**. Esgotado o orçamento sem
atingir o critério mínimo de `avaliacao_spec.md`, o diagnóstico é registrado
(seção 10) e a decisão sobre ampliar dados ou rever o gerador volta ao
usuário — não se continua treinando indefinidamente.

---

# 9. Reprodutibilidade e artefatos

Conforme `avaliacao_spec.md`, seção 2.4, e `ai_development_rules.md`, seção
9.1.

## 9.1 Sementes e determinismo

| Item | Definição |
|---|---|
| Semente global | `random`, `numpy` e `torch` (CPU e CUDA) fixadas |
| `DataLoader` | `worker_init_fn` e `generator` com semente derivada |
| Algoritmos | `torch.use_deterministic_algorithms(True, warn_only=True)`; operações não determinísticas são listadas no registro |

Não se promete igualdade bit a bit entre máquinas. Promete-se que a mesma
semente, dataset e configuração, na mesma máquina, repetem as métricas dentro
de 0,2 pp de erro percentual, e isso é verificado por um teste de repetição
no experimento E0.

## 9.2 Registro de cada execução

Gravado em `execucao.json`, na pasta da execução, fora do repositório:

| Campo | Conteúdo |
|---|---|
| `identificador` | Data e hora, mais um sufixo curto |
| `commit_git` | Commit do código, e se havia alterações não commitadas |
| `semente_global` | Valor usado |
| `dataset` | Caminho, hash SHA-256 do `metadados.jsonl` e sementes de geração por conjunto |
| `configuracao` | Todos os hiperparâmetros efetivos, inclusive lote por passo, lote efetivo e pesos de classe calculados |
| `bibliotecas` | Versões de `torch`, `segmentation_models_pytorch`, `albumentations`, `torchmetrics`, `numpy`, `opencv-python` e Python |
| `hardware` | GPU, VRAM e versão do driver CUDA |
| `metricas_por_epoca` | Perda e métricas de validação, em CSV ao lado |
| `melhor_ponto` | Época, critério da seção 4.3 e caminho do checkpoint |
| `modelo_versao` | Conforme `modelo_spec.md`, seção 8.1 |

## 9.3 Checkpoint

Arquivo `.pt`, que a ML07 lê sem depender do código de treino:

```text
state_dict      pesos do modelo
arquitetura     {"nome": "Unet", "encoder": "resnet34", "classes": 3}
entrada         {"largura": 768, "altura": 576}
normalizacao    {"media": [...], "desvio": [...]}
classes         ["fundo", "placa_limpa", "placa_coberta"]
```

Versões: `v0.x.y` para execuções experimentais; `v1.0.0` só para o modelo que
cumprir `avaliacao_spec.md`, seção 4.1. A cópia em uso fica em
`models/checkpoints/latest.pt`, ignorada pelo Git
(`ai_development_rules.md`, seção 9.4).

## 9.4 Organização do código

Módulos separados em `backend/training/` (`ai_development_rules.md`, seção
9.2): dados, aumentos, perda, modelo, métricas, loop de treino e linha de
comando. A configuração fica em arquivo versionado, passado à linha de
comando; nenhum hiperparâmetro é fixado no código do loop.

---

# 10. Diagnóstico e riscos

## 10.1 Domain gap

O dataset é sintético e **não há fotos reais** da empresa parceira. Os
resultados do treino valem para o domínio sintético. Sintético bom e real
ausente significa "o modelo aprendeu o gerador", não "o modelo funciona em
campo". Isso deve constar como limitação explícita em qualquer relatório, e a
validação em campo permanece pendente até o material descrito em
`current_task_externo.md` (EXT01).

## 10.2 Atalho pelos recortes

Os sprites são recortados automaticamente de fotos naturais; as bordas
recortadas têm características próprias (serrilhado, halo de fundo residual).
Um modelo pode aprender "borda de recorte = inseto" em vez de forma de inseto,
e falharia diante de insetos reais capturados na cola. Mitigações: variação de
suavização de borda no gerador, desfoque e compressão na augmentation, e
verificação manual por amostragem das predições na validação.

## 10.3 Atalho por cor ou idade

Antes de aprovar, o treino executa uma verificação: o erro percentual de
validação, agrupado por idade simulada e por faixa de cor dominante, não deve
variar de modo sistemático com essas variáveis. Uma tendência clara indica que
o modelo usa a cor de fundo como atalho (`modelo_spec.md`, seção 4.2.2).

## 10.4 Objetos pequenos

Um mosquito de cerca de 8 pixels em 768 × 576 sofre com o redimensionamento e
com a compressão do encoder. Se o erro se concentrar em imagens com muitos
objetos pequenos, `modelo_spec.md`, seção 11, prevê revisar a resolução; isso
exige novo ciclo de geração e treino e é uma decisão a registrar.

## 10.5 Critério de parada

O projeto para de treinar quando **uma** destas condições é verdadeira:

1. o modelo cumpre o alvo sintético de `avaliacao_spec.md`, seção 4.1, no
   conjunto de validação e depois, uma única vez, no teste sintético;
2. o orçamento de 8 treinos completos se esgota (seção 8);
3. a curva de aprendizado de E5 mostra que mais dados não melhoram a
   validação e o critério não foi atingido: o diagnóstico vai ao usuário.

---

# 11. Decisões que dependem de validação

Valores marcados como hipótese neste documento, com o experimento que os
decide:

| Decisão | Valor inicial | Experimento |
|---|---|---|
| Pré-treino ImageNet | ativo | E1 |
| `BatchNorm` do encoder em modo de avaliação | ativo | E2 |
| Expoente e teto dos pesos de classe | 0,5 e 10 | E3 |
| Termo de área `λ` | 0 | E4 |
| Volume do dataset | 3.000 | E5 |
| Taxas de aprendizado, decaimento, épocas e paciência | seção 4 | Ajuste fino durante E1 a E4, sempre na validação |
| Lote por passo | maior que caiba | Medido antes do treino |
| Resolução de entrada | 768 × 576 | Revisada só se o erro se concentrar em objetos pequenos (seção 10.4) |

---

# 12. Pendências

- [ ] Gerador: registrar por imagem a fração de área coberta por grupo de
      inseto, para a análise de erro por grupo
- [ ] Gerador: gerar os subconjuntos de teste de robustez (ML06) com sementes
      disjuntas das de treino
- [ ] Dependência de treino: instalar a versão de `torch` com CUDA no grupo
      `treino` e verificar a GPU antes do primeiro treino
- [ ] Definir o volume mínimo de fotos reais para o teste real
      (`avaliacao_spec.md`, seção 7)

---

# FIM DO PIPELINE DE TREINO
