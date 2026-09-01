# DATASET SINTÉTICO — Projeto Integrador

**Versão:** 1.0
**Status:** ATIVO
**Escopo:** geração do dataset sintético de treino — fonte de sprites, geração
de fundo, composição, metadados e critérios de aceite

---

# 1. Objetivo

Especificar de forma fechada o gerador de imagens sintéticas de armadilhas
adesivas usado para treinar o modelo de segmentação (Fase 1, conforme
`../foundation/project_overview.md`, seção 8.1).

Este documento consolida os nove requisitos acumulados ao longo da
especificação técnica (tabela da seção 8.1 citada acima) em um pipeline
único e implementável. Nenhum requisito anterior é reaberto aqui — cada um é
referenciado, não redecidido.

---

# 2. Estratégia geral

O gerador combina duas fontes de conteúdo, que **não têm a mesma origem**:

| Componente | Origem | Motivo |
|---|---|---|
| Sprites de inseto | Recortes de datasets públicos existentes | Não existe dataset pronto da cena completa (armadilha + inseto); mas existem fotos reais de insetos isolados, o que evita desenhar/gerar insetos do zero |
| Cena de fundo (placa, moldura, iluminação, envelhecimento, sujeira) | Gerada por código | É específica demais do nosso equipamento — nenhum dataset público reproduz um refil de 450×220mm sob luz BL UVA |

Um dataset de armadilha adesiva pronto para uso **não existe** — a estratégia
de "separar imagens boas de datasets consolidados", cogitada inicialmente,
não se aplica à cena inteira. Aplica-se apenas à fonte dos sprites, descrita
na seção 3.

---

# 3. Fonte dos sprites de inseto

## 3.1 Datasets candidatos

| Fonte | O que oferece | Uso |
|---|---|---|
| Roboflow Universe — datasets de armadilha adesiva agrícola (mosca-branca, pulgão, em cartão amarelo) | Insetos já fotografados **colados a uma superfície adesiva**, silhueta realista de inseto preso, alguns com máscara de segmentação pronta | Fonte primária — a pose de "inseto grudado" é o que mais se aproxima da nossa cena real |
| iNaturalist (subconjunto CC) | Fotos de mosquitos e moscas isoladas, alta variedade de espécies e ângulos | Fonte secundária — precisa de remoção de fundo manual/automática |
| Kaggle "Mosquito Alert" e datasets correlatos | Fotos de Aedes/Culex | Fonte secundária, mesmo tratamento |

## 3.2 Processamento dos sprites

```text
Imagem fonte (dataset público)
        ↓
Remoção de fundo (rembg ou segmentação manual para casos difíceis)
        ↓
Recorte na silhueta (PNG com canal alfa)
        ↓
Catalogação: espécie/tipo (se disponível), fonte, licença
        ↓
Banco de sprites
```

## 3.3 Regras de catalogação

| Regra | Definição |
|---|---|
| Licença | Registrar a licença de cada sprite na origem (CC-BY, CC-BY-NC, etc.); nenhum sprite sem licença identificada entra no banco |
| Variedade mínima | Banco deve conter ao menos três categorias de tamanho — pequeno (drosófila/mosquito), médio (mosca comum), grande (mariposa/besouro) — conforme a taxonomia de `../model/modelo_spec.md`, seção 3.2 |
| Qualidade de recorte | Bordas do recorte devem ser nítidas; sprites com halo ou fundo residual visível são descartados, não corrigidos manualmente pixel a pixel |

## 3.4 Fragmentos

A taxonomia (`modelo_spec.md`, seção 3.2) determina que fragmentos de inseto
contam como área coberta. O banco de sprites deve incluir uma fração de
sprites já fragmentados (asa isolada, silhueta parcial) — obtidos recortando
uma sub-região de um sprite inteiro — para que o gerador os utilize sem
depender de fragmentação em tempo de composição.

---

# 4. Geração do fundo sintético

## 4.1 Estrutura geométrica

| Elemento | Definição |
|---|---|
| Placa | Retângulo interno, proporção 450:220 (≈2,05:1), conforme `../foundation/hardware_armadilha.md`, seção 3.1 |
| Moldura | Região ao redor da placa, variando em proporção e enquadramento — nunca ausente, nunca com proporção fixa (requisito da tabela, linha 1) |
| Resolução de geração | Gerar em resolução superior à de entrada do modelo (`../model/modelo_spec.md`, seção 6) e reamostrar no pipeline de treino, preservando qualidade para eventual revisão futura de resolução |

## 4.2 Cor e iluminação

Implementa o requisito de variação agressiva de dominante de cor
(`modelo_spec.md`, seção 4.1):

| Parâmetro | Faixa de variação |
|---|---|
| Dominante de cor | De forte viés violeta-azulado a branco corrigido (simulando diferentes balanços de branco de câmera) |
| Gradiente de iluminação | Intensidade e direção variáveis, simulando fontes pontuais próximas (as três lâmpadas) |
| Reflexo especular | Presente em subconjunto das amostras, posição e intensidade variáveis |
| Sombra da moldura sobre a placa | Presente em subconjunto das amostras |

## 4.3 Envelhecimento do refil

Implementa os requisitos de amarelecimento (`modelo_spec.md`, seções 4.2.1 e
4.2.2):

```text
idade_simulada ~ Uniforme(0, IDADE_MAXIMA_DIAS)

tom_amarelecimento = f(idade_simulada)       # progressão de cor
luminancia_placa   = g(idade_simulada)       # progressão de brilho, decrescente

percentual_cobertura ~ Uniforme(0, 100)      # AMOSTRADO INDEPENDENTEMENTE

# nenhuma correlação entre idade_simulada e percentual_cobertura
```

**Regra crítica:** `idade_simulada` e `percentual_cobertura` são amostrados
por distribuições independentes, nunca derivados um do outro. Violar isso
reintroduz o risco de correlação espúria já identificado — o motivo pelo
qual esta regra existe está documentado em `modelo_spec.md`, seção 4.2.2, e
não é repetido aqui.

`idade_simulada` é persistida como metadado por amostra (seção 6).

## 4.4 Distratores (sujeira)

Implementa o requisito da seção 3.4 de `modelo_spec.md`:

| Distrator | Frequência de inclusão |
|---|---|
| Poeira/manchas difusas | Alta — presente na maioria das amostras, intensidade variável |
| Teia de aranha | Baixa — subconjunto menor, mas não ausente |
| Pelos/fibras | Baixa |
| Respingos (contexto açougue) | Baixa a moderada |

Todo distrator é desenhado na imagem e **ausente da máscara** — é o que
ensina o modelo a não classificar sujeira como inseto.

---

# 5. Composição

## 5.1 Pipeline de composição

```text
Fundo sintético (seção 4)
        ↓
Seleciona N sprites do banco (N ~ função do percentual_cobertura alvo)
        ↓
Posiciona cada sprite: posição, escala, rotação aleatórias, dentro da placa
        ↓
Máscara de cada sprite é combinada por UNIÃO (não soma) — ver seção 5.2
        ↓
Ajusta N iterativamente até a área da união atingir percentual_cobertura alvo
        ↓
Aplica distratores (seção 4.4) sobre a composição, sem alterar a máscara
        ↓
Imagem final + máscara de 3 classes (fundo / placa_limpa / placa_coberta)
```

## 5.2 Regra de união

Implementa `modelo_spec.md`, seção 3.3. A máscara de `placa_coberta` é a
união booleana das silhuetas dos sprites posicionados — sobreposição entre
sprites não soma área duas vezes. O percentual de cobertura reportado como
metadado é sempre medido **na máscara final**, nunca estimado pela soma das
áreas individuais dos sprites antes da composição.

## 5.3 Convergência do percentual alvo

Como sprites se sobrepõem, o número de sprites necessário para atingir um
percentual alvo não é previsível de antemão. O algoritmo adiciona sprites
iterativamente, medindo a área da máscara após cada inserção, até atingir a
tolerância definida (± 2 pontos percentuais do alvo) ou um limite máximo de
tentativas — evitando loop infinito em percentuais muito altos onde a
sobreposição dificulta a convergência.

---

# 6. Metadados por amostra

Cada imagem gerada é acompanhada de um registro estruturado:

| Campo | Descrição |
|---|---|
| `id` | Identificador único da amostra |
| `semente` | Semente de geração — usada para a divisão dos conjuntos (`../model/avaliacao_spec.md`, seção 2.3) |
| `percentual_cobertura_real` | Medido na máscara final, não no alvo solicitado |
| `idade_simulada_dias` | Conforme seção 4.3 |
| `n_sprites` | Número de sprites utilizados |
| `distratores_presentes` | Lista dos tipos de distrator incluídos |
| `dominante_cor` | Parâmetro de cor aplicado (seção 4.2) |

O metadado é o que viabiliza a estratificação por faixa de cobertura e a
análise de erro por idade do refil, exigidas em `../model/avaliacao_spec.md`.

---

# 7. Estratificação e volume

## 7.1 Estratificação por cobertura

Conforme `../model/avaliacao_spec.md`, as amostras são estratificadas por
faixa de cobertura, alinhadas aos limiares de status
(`../foundation/project_overview.md`, seção 7.2):

| Faixa | Proporção alvo do dataset |
|---|---|
| 0–40% (`ok`) | 1/3 |
| 40–70% (`atencao`) | 1/3 |
| 70–100% (`trocar`) | 1/3 |

Distribuição uniforme entre faixas, não proporcional a uma distribuição real
assumida — o objetivo é garantir exemplos suficientes nas fronteiras de
decisão (40% e 70%), onde o erro do modelo tem maior consequência prática.

## 7.2 Volume

| Item | Valor |
|---|---|
| Volume inicial do dataset sintético | 3.000 imagens |
| Divisão | 70/15/15 conforme `avaliacao_spec.md`, seção 2.2 |

O volume inicial é um ponto de partida, não um valor final — pode ser
ampliado se a avaliação (seção 4 de `avaliacao_spec.md`) não atingir os
critérios mínimos.

---

# 8. Calibração pendente

Este gerador é construído **sem** referência visual direta do refil real —
a pendência já registrada em `../foundation/hardware_armadilha.md`, seção 5.
Isso significa que os parâmetros de cor, textura e proporção são estimativas
razoáveis, não medições.

Quando a foto real chegar, a calibração necessária é:

1. Ajustar a faixa de dominante de cor (seção 4.2) para o que a câmera real
   captura sob a iluminação real.
2. Confirmar a proporção exata e textura da superfície do refil.
3. Comparar estatisticamente uma amostra do dataset sintético com a foto
   real (histograma de cor, textura) antes de iniciar o treino definitivo.

Treinar antes dessa calibração é aceitável para validar o pipeline
tecnicamente, mas o resultado não deve ser tratado como métrica final —
apenas como teste de fumaça do gerador e do treino.

---

# 9. Critérios de aceite do gerador

| Critério | Verificação |
|---|---|
| Todos os nove requisitos da tabela em `project_overview.md`, seção 8.1, implementados | Checklist manual contra este documento |
| Máscara de 3 classes gerada corretamente | Inspeção visual de amostra aleatória |
| `idade_simulada` e `percentual_cobertura` sem correlação | Calcular correlação de Pearson entre as duas colunas de metadados; deve ser próxima de zero |
| Distratores presentes e ausentes da máscara | Inspeção visual de amostra com distrator |
| Reprodutibilidade | Gerar duas vezes com a mesma semente global produz dataset idêntico |

---

# 10. Pendências

- [ ] Escolher e testar a ferramenta de remoção de fundo para os sprites
      (ex.: rembg) e definir limiar de qualidade de recorte
- [ ] Levantar e catalogar os datasets de origem dos sprites, com licença
- [ ] Definir `IDADE_MAXIMA_DIAS` simulada (depende de referência real, ver
      seção 8)
- [ ] Calibrar com foto real do refil quando disponível (seção 8)

---

# FIM DO DATASET SINTÉTICO
