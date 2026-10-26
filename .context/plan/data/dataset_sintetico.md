# DATASET SINTÉTICO — Projeto Integrador

**Versão:** 1.2
**Status:** ATIVO
**Escopo:** geração do dataset sintético de treino — recomposição com insetos
reais, modo legado de sprites, metadados e critérios de aceite

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
| Insetos da recomposição principal | Componentes da classe `placa_coberta` recortados das placas reais UMS | Preserva pose presa à cola, escala, câmera e iluminação da fonte |
| Bases de recomposição | Placas reais de baixa cobertura e refis StickFly K-45 sintéticos, alternados por padrão em 50/50 | A mistura reduz o atalho da grade que aparece nas placas UMS |
| Banco anterior de sprites | Catálogo público e licenciado, mantido no modo legado | Continua disponível para comparação e não é removido |

O modo principal recompõe imagens de armadilhas com recortes reais. O modo de
sprites permanece disponível para comparações e execuções antigas.

---

# 3. Fonte dos sprites de inseto

## 3.1 Datasets candidatos

| Fonte | O que oferece | Uso |
|---|---|---|
| UMS, Ong & Lim (2025), CC BY 4.0, DOI `10.6084/m9.figshare.28280792.v1` | 2.471 sprites PNG reais, escala conhecida de 23,62 px/mm e classes taxonômicas | Fonte principal; atribuição e metadados completos acompanham o catálogo externo |
| Sprites Amazônia, CC BY 4.0, DOI `10.6084/m9.figshare.28688198` | 246 sprites macro reais, recortados e redimensionados | Fonte complementar; escala física desconhecida, tamanho estimado pela distribuição UMS do grupo equivalente |

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
| Grupos de inseto | O banco reúne todos os grupos relevantes em estabelecimentos brasileiros: moscas (doméstica, varejeira, drosófila), mosquitos (*Culex*, *Aedes*), formigas, baratas, mariposas e besouros pequenos. Cada sprite registra o `grupo` no manifesto, para ponderar a composição (voadores dominam o refil UV) e para analisar o erro por grupo |
| Qualidade de recorte | Bordas do recorte devem ser nítidas; sprites com halo ou fundo residual visível são descartados, não corrigidos manualmente pixel a pixel |
| Escala física | Cada item registra `tamanho_mm` ou `px_por_mm`, a categoria derivada do comprimento e se a escala é medida ou estimada |

O refil mede 450 × 220 mm e ocupa aproximadamente 720 × 352 px em uma cena
768 × 576 (cerca de 1,6 px/mm). O UMS foi extraído em `escala = 0,5` de scans
de 1.200 dpi, equivalente a 23,62 px/mm; portanto, o maior lado do sprite em
pixels dividido por 23,62 fornece seu tamanho estimado em milímetros. Para os
sprites Amazônia, o tamanho é sorteado da distribuição UMS do grupo equivalente.
O fator de aparência por amostra é `k ∈ [1,3; 3,0]`, log-uniforme, e o tamanho
renderizado usa `mm × px_por_mm × k × U(0,85; 1,2)`.

O conversor `backend/training/importar_sprites_reais.py` grava o catálogo em
`D:\dados\trapsight\sprites-reais`; PNGs e metadados ficam fora do repositório.
As cópias devem preservar autoria, fonte, licença CC BY 4.0 e os links DOI no
manifesto.

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
| Dominante de cor | Faixa creme/amarelada plausível, envelhecendo de amarelo claro a creme escuro, sem matizes verdes ou violeta fortes |
| Gradiente de iluminação | Intensidade e direção variáveis, hotspot UV e vinheta suaves |
| Textura | Manchas, fibras e textura da cola discretas, sem contaminar o gabarito |
| Sombra | Sombra suave da moldura e sombra curta de contato sob cada inseto |

## 4.3 Envelhecimento do refil

Implementa os requisitos de amarelecimento (`modelo_spec.md`, seções 4.2.1 e
4.2.2):

```text
idade_simulada ~ Uniforme(0, IDADE_MAXIMA_DIAS)

tom_amarelecimento = f(idade_simulada)       # progressão de cor
luminancia_placa   = g(idade_simulada)       # progressão de brilho, decrescente

percentual_cobertura_alvo ~ uniforme dentro de 0–10, 10–20 ou 20–35%

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

Sujeira confirmada nas fotografias também permanece na classe 1, registrada
como revisada. A classe 255 é reservada a regiões ambíguas; não pode substituir
os exemplos negativos de sujeira. Marcações impressas, grade e bordas têm
máscaras de estrutura próprias, separadas dos insetos e dos distratores.

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
iterativamente e mede a união após cada inserção até ficar a até 0,5 ponto
percentual do alvo. A composição é limitada a 35% e registra `alvo_atingido`;
amostras fora da tolerância devem ser rejeitadas na validação do conjunto.

## 5.4 Recomposição com insetos reais

O modo principal recebe `--placas-reais` apontando para um conjunto com
`imagens/`, `mascaras/` e `metadados.jsonl`. Antes de abrir máscaras ou recortar
componentes, o gerador separa os identificadores das placas por uma semente
reprodutível. Por padrão, 80% ficam em composição e 20% em avaliação. As seis
placas de baixa cobertura indicadas pelo inventário ficam obrigatoriamente em
composição; se o inventário mudar, as bases restantes são escolhidas pela menor
cobertura rotulada. Nenhum recorte ou base de avaliação entra em uma amostra.

As placas de composição são então atribuídas a treino, validação e teste,
antes de abrir pixels, estratificando separadamente as seis bases. Cada placa
tem um único dono, inclusive quando fornece simultaneamente base e recortes.
Com as fontes atuais, são 39/8/8 placas e 4/1/1 bases. A amostra usa essa divisão
explicitamente; um único fundo real em validação e teste oferece pouca
diversidade. Antes do conjunto definitivo, decidir entre ampliar o inventário
de bases independentes ou usar bases sintéticas nesses conjuntos. A reserva
de 14 placas reais continua intocada.

Da classe `placa_coberta` são extraídos componentes conectados com área mínima
de 25 pixels e razão entre lados de até 4:1. A máscara do componente vira o
canal alfa do recorte, sem alterar pixels, cor ou brilho. A composição permite
somente giros em múltiplos de 90° e espelhamento horizontal. O centro de cada
recorte precisa cair dentro da placa erodida em 26 pixels. A sobreposição é
permitida e usada para atingir altas coberturas.

As bases reais vêm somente das placas de composição com menor carga rotulada.
As bases sintéticas seguem o formato 450:220 do StickFly K-45, sem grade,
superfície `(232, 230, 221)`, ruído gaussiano de sigma 4 misturado a 10% e
amarelecimento suave das bordas em direção a `(206, 194, 152)`. A proporção de
bases reais é configurável e começa em 50%; a sequência distribui os dois
tipos uniformemente ao longo do conjunto.

O alvo é sorteado antes da quantidade de colagens. No modo real, `trocar` cobre
20–55%, limitando o alvo à capacidade verificada após a separação das fontes;
os modos legados de sprites continuam
limitados às faixas anteriores. Em `ok` e `atencao`, a colocação é quase uniforme
com espaçamento mínimo, sem focos. Em `trocar`, o padrão é uniforme com
sobreposição. Qualquer hipótese com focos exige comparação contra colocação
aleatória uniforme na mesma densidade e justificativa explícita. A mesma fonte
pode aparecer no máximo doze vezes em uma amostra no modo real, com até
12.000 colagens. Isso compensa o banco menor de validação e teste, mas aumenta
a repetição dentro da amostra e deve ser acompanhado no relatório. Quando a
fase espaçada não alcança o alvo, a execução informa a limitação em vez de
criar focos silenciosamente. O relatório
registra a origem dos recortes, os parâmetros geométricos, a maior reutilização
no conjunto, a cobertura herdada pela base e a cobertura adicionada pela
composição, sempre medidas na máscara final.

Nas bases sintéticas, poeira, teias, pelos e respingos são desenhados antes
dos insetos, nas frequências da seção 4.4. Seus pixels permanecem na classe 1;
se um inseto for colado sobre eles, somente a silhueta do inseto vira classe 2.

As máscaras originais UMS são estimadas e cobrem somente 25,6% das anotações COCO. O
gerador avalia `cv2.inpaint` apenas nas regiões rotuladas da base; essa operação
não remove insetos sem rótulo e não há imagem limpa correspondente para
validar reconstruções. Por isso, a base permanece sem inpainting e as duas
parcelas de cobertura são reportadas separadamente.

As seis bases recebem máscaras complementares em diretório próprio, sem
substituir as originais. Cada placa tem uma máscara de estruturas versionada
(grade, etiqueta, logomarca e borda), desenhada e revisada separadamente. Não
se descartam componentes grandes por tamanho: insetos grandes precisam entrar.
O contorno físico da placa é revisado; buracos de classe 0 causados por insetos
sobre a placa são corrigidos com a segmentação do inseto.

Candidatas são regiões 8-conexas com cinza em ponto fixo
`(4899R + 9617G + 1868B + 8192) >> 14` abaixo da mediana na placa menos 35,
fora das estruturas. O limiar localiza caixas para SAM, sem decidir a classe.
A decisão semântica de cada região fica em arquivo versionado por placa:
inseto → 2; sujeira confirmada → 1; ambígua → 255. Não há redimensionamento.
O baseline continua usando um único limiar global independente deste processo.

O aceite é por placa: nenhuma candidata sem decisão; área candidata ambígua
de no máximo 10% da área candidata e no máximo 0,2 ponto percentual da placa.
O relatório discrimina regiões e áreas antes/depois por decisão e mostra a
imagem original junto da sobreposição colorida. Contagem de componentes
resolvidos sozinha não comprova completude do rótulo.

Pixels 255 não entram na entropia cruzada, Dice, termo de área, percentual,
pesos de classe nem métricas. A configuração e cada amostra registram a versão
da máscara usada pela base; a configuração também registra seu SHA-256.
As 14 placas de avaliação permanecem com rótulos incompletos, limitação
obrigatória em qualquer relatório de avaliação real.

---

# 6. Metadados por amostra

Cada imagem gerada é acompanhada de um registro estruturado:

| Campo | Descrição |
|---|---|
| `id` | Identificador único da amostra |
| `semente` | Semente de geração — usada para a divisão dos conjuntos (`../model/avaliacao_spec.md`, seção 2.3) |
| `percentual_cobertura_alvo` | Alvo sorteado na faixa estratificada |
| `percentual_cobertura_real` | Medido na máscara final, não estimado pela soma dos sprites |
| `alvo_atingido` | Indica diferença dentro da tolerância do modo (0,5 pp no legado; 1 pp na recomposição real) |
| `idade_simulada_dias` | Conforme seção 4.3 |
| `n_sprites` | Número de sprites utilizados |
| `n_recortes` | Número de recortes reais colados na recomposição |
| `origem_base`, `placa_base_id` | Tipo da base e identificador da placa real, quando houver |
| `mascara_base_versao` | Versão e hash da máscara complementar ou indicação explícita de rótulo original incompleto |
| `cobertura_herdada_base_percentual` | Classe 2 já presente na máscara da base antes da recomposição |
| `cobertura_adicionada_percentual` | Área de novos recortes que não se sobrepõe à cobertura herdada |
| `placas_origem_recortes` | Placas de composição que forneceram recortes à amostra |
| `fracao_aglomerada` | Fração de área coberta em componentes maiores que 500 pixels |
| `px_por_mm`, `k_escala` | Escala física observada da placa e fator de aparência sorteado |
| `pesos_grupo` | Pesos efetivos de grupo usados na composição |
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
| 0–10% (`ok`) | 1/3 |
| 10–20% (`atencao`) | 1/3 |
| 20–55% (`trocar`) no modo de recomposição real | 1/3 |

Distribuição uniforme entre faixas, não proporcional a uma distribuição real
assumida — o objetivo é garantir exemplos suficientes nas fronteiras de
decisão (10% e 20%), onde o erro do modelo tem maior consequência prática.

A recomposição real limita o alvo a **55%** após particionar o banco por
placa; a referência de 62,62% com 2.200 colagens continua sendo uma referência
de calibração, sem ser apresentada como cobertura garantida deste banco.
O modo legado de sprites permanece limitado a 35%.

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
| Sem vazamento entre placas | Conferir que `placas_origem_recortes` e `placa_base_id` não intersectam as placas de avaliação listadas no relatório |
| Sem vazamento entre treino, validação e teste | Cada placa de composição pertence a exatamente um conjunto; a união de bases e origens de recortes de um conjunto é disjunta dos demais. O carregador deve recusar cruzamentos, inclusive entre os papéis de base e recorte |
| Bases com rótulos revisados | Aplicar o aceite por área e decisão da seção 5.4 em cada placa; registrar regiões, áreas, versões e hashes, preservando as originais |
| Classe ignorada | Perturbar predições somente em pixels 255 não altera perda nem métricas e produz gradiente zero nesses pixels |
| Cobertura real e heredada corretas | Recalcular `percentual_cobertura_real`, cobertura herdada e área adicionada pelas máscaras gravadas |
| Similaridade dos recortes | Comparar a distribuição do maior lado dos componentes escuros por KS contra as placas de avaliação; registrar a distância |
| Similaridade de tons | Comparar histogramas de tons de cinza com 32 faixas usando meia distância L1 |
| Fração escura | Comparar a fração com cinza abaixo de 110 contra 0,0635; medir somente pixels da placa |
| Aglomeração sem grade | Fração dos pixels escuros (<110) em componentes >500 px após remover segmentos horizontais/verticais de pelo menos 41 px. Referência nas 69 placas: 0,016 sem grade; com grade, aproximadamente 0,72. A antiga referência 0,777 incluía estruturas e foi invalidada |
| Ocupação espacial | Fração dos tiles de 24 px elegíveis (>=50% de placa válida) com pelo menos 3 pixels escuros. Comparar por densidade escura: ocupação real 0,35 em 1–2%, 0,57 em 2–4% e 0,88 em 4–8% |
| Completude por área e decisão | Em cada base: zero candidatas sem decisão, área ambígua <=10% da área candidata e <=0,2 pp da placa; estruturas versionadas; sujeira revisada na classe 1; inseto sobre a placa nunca na classe 0 |
| Quantidade de componentes de referência | Registrar as 5.144 componentes escuros identificadas nas 69 placas |
| Relatório visual | Gravar os quatro descritores somente dentro da placa, a cobertura das amostras usadas na comparação de aglomeração, a divisão e semente das placas, a maior reutilização de recorte e a conclusão do teste de inpainting em `relatorio_geracao.json` |

A classe 2 é a medida exata da máscara gerada. Nas placas reais, as máscaras
SAM cobrem somente 25,6% das anotações COCO; por isso, a comparação de
aglomeração também registra os componentes dos pixels escuros como aproximação
visual e informa separadamente a fração calculada pela máscara rotulada.

Não há referência real validada de insetos acima de aproximadamente 8% de pixels escuros. O
domínio `trocar` de 20–70% de cobertura é extrapolação; o perfil limitado a
20–55% é um subintervalo desse domínio, sem validação visual real nessa faixa.
Não se compara aglomeração a uma suposta referência real de cobertura >=50%.
Na amostra de 30, medir todas as imagens, comparar `trocar` com o aleatório e
parar para revisão. No conjunto de 3.000, autorizado separadamente, medir pelo
menos 100 amostras com os mesmos instrumentos versionados e testados.

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
