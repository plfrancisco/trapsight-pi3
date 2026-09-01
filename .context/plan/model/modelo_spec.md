# MODELO E INFERÊNCIA — Projeto Integrador

**Versão:** 1.0
**Status:** ATIVO
**Escopo:** arquitetura do modelo, pré-processamento, cálculo do percentual e
carregamento de pesos

---

# 1. Objetivo

Especificar de forma fechada o pipeline de inferência: o que entra, como é
transformado, como o percentual é calculado e como o modelo é carregado.

Nada aqui deve exigir interpretação durante a implementação.

---

# 2. Segmentação em três classes

## 2.1 Decisão

O modelo produz segmentação de **três classes**, não binária:

| Classe | Índice | Significado |
|---|---|---|
| `fundo` | 0 | Tudo fora da superfície adesiva — moldura da armadilha, parede, ambiente |
| `placa_limpa` | 1 | Superfície adesiva sem insetos, **incluindo áreas com sujeira** |
| `placa_coberta` | 2 | Superfície adesiva ocupada por **insetos** |

## 2.2 Justificativa

A alternativa seria segmentação binária (coberto vs. não coberto), assumindo
que a imagem já vem recortada exatamente na superfície adesiva. Foi rejeitada.

O percentual é `área coberta ÷ área da placa`. Com segmentação binária, o
denominador só pode ser a imagem inteira — o que exige que o enquadramento
esteja perfeito. Qualquer margem de parede ou moldura branca na foto entra no
denominador e **subestima o percentual**, sem que nada no sistema indique o
erro.

Com três classes, o denominador é a área que o próprio modelo identificou como
placa. O enquadramento deixa de importar, e o resultado permanece correto
mesmo com margem ao redor.

O custo é um canal adicional na saída da rede. A arquitetura, o treino e o
pipeline permanecem os mesmos.

**Consequência para o dataset sintético:** as imagens geradas devem incluir
margem de fundo ao redor da placa, com variação de enquadramento. Uma placa
que preenche todo o quadro em 100% das amostras impediria o modelo de aprender
a classe `fundo`.

---

# 3. Definição de área coberta

**Área coberta é exclusivamente área ocupada por insetos ou fragmentos de
insetos.** Sujeira, resíduo e manchas pertencem à classe `placa_limpa`, ainda
que sejam visualmente escuros.

## 3.1 Justificativa

O produto mede a **capacidade restante de captura**, não o estado estético da
superfície. Uma armadilha instalada em ambiente empoeirado acumularia sujeira
sem capturar insetos; se sujeira contasse, o sistema recomendaria a troca de um
refil ainda plenamente funcional.

A métrica passaria a medir contaminação ambiental em vez de desempenho da
armadilha — e desempenho é o que a empresa entrega ao cliente.

## 3.2 Taxonomia

Classificação de tudo que pode aparecer sobre a superfície adesiva.

### Conta como `placa_coberta`

| Item | Observação |
|---|---|
| Mosquitos e moscas | Alvo principal |
| Insetos grandes — mariposas, besouros, vespas | Ocupam área desproporcional; uma mariposa equivale a dezenas de mosquitos |
| Insetos muito pequenos — drosófilas, formigas aladas | Relevantes em açougue e hortifrúti; ocupam poucos pixels na resolução de entrada |
| **Fragmentos** — asas soltas, pernas, corpos parciais | Ocupam a cola e reduzem a captura como um inseto inteiro. Regra deliberadamente simples, para manter consistência entre anotadores |
| Insetos sobrepostos | Ver regra de união na seção 3.3 |

### Conta como `placa_limpa`

| Item | Contexto em que aparece |
|---|---|
| Poeira e sujeira | Qualquer ambiente |
| Gordura aerossolizada | Açougue e cozinha; forma película que amarela a superfície |
| Respingos de sangue ou líquidos | Açougue |
| **Teia de aranha** | Comum em armadilhas adesivas; não é captura |
| Pelos, fibras e penas | Objetos escuros e alongados, mas não são insetos |
| Marcações impressas do refil | Logotipo ou texto do fabricante, se houver |
| Vinco, dobra ou rasgo do refil | Artefato de instalação |
| Bolhas de ar sob o adesivo | Artefato de instalação |

### Não pertence à placa — classe `fundo`

Moldura da armadilha, parede, lâmpadas visíveis e qualquer elemento do
ambiente.

## 3.3 Regra de sobreposição

Quando insetos se sobrepõem, a área coberta é a **união** das regiões, nunca a
soma das áreas individuais.

Somar áreas individuais infla o gabarito, e o erro cresce com a densidade —
justamente nas placas próximas da saturação, onde a medição precisa ser
confiável. Na geração sintética, a máscara deve ser composta por união de
silhuetas, não por acúmulo.

## 3.4 Consequências técnicas

Insetos e sujeira são, ambos, regiões escuras sobre fundo branco. A distinção
**não pode ser feita por cor ou brilho**; depende de forma, textura e
morfologia — insetos têm contorno definido e estrutura reconhecível, sujeira é
amorfa e difusa.

| Exigência | Detalhe |
|---|---|
| Dataset sintético | Deve conter sujeira, teia, pelos e respingos como **distratores** — presentes na imagem, ausentes da máscara. Sem exemplos negativos, o modelo classificará qualquer mancha escura como inseto |
| Anotação de fotos reais | Segue a taxonomia da seção 3.2. Casos não previstos devem ser registrados e a taxonomia atualizada, nunca decididos individualmente pelo anotador |

Esta é também a limitação central do baseline por luminosidade — ver seção 9.2.

**Nomenclatura:** os identificadores `placa_coberta` e `percentual_coberto`
permanecem, mas seu significado é o definido nesta seção. "Coberta" refere-se
sempre a cobertura por insetos.

---

# 4. Condições visuais a tolerar

Fenômenos ópticos presentes nas fotos reais que o modelo precisa suportar. Todos
devem estar representados no dataset sintético.

| Condição | Origem | Risco se ausente do treino |
|---|---|---|
| **Dominante de cor azul-violeta** | Iluminação BL UVA | Ver seção 4.1 |
| **Amarelamento do adesivo** | Exposição contínua à luz UV | Ver seção 4.2 |
| **Reflexo especular** | As três lâmpadas ficam próximas à superfície | Região estourada pode ser lida como buraco na placa |
| Sombra da moldura sobre a placa | Geometria da armadilha | Região escura interpretada como inseto |
| Gradiente de iluminação | Lâmpadas pontuais, não difusas | Um lado da placa sistematicamente mais escuro |
| Desfoque e ruído | Limitação da câmera | |

## 4.1 A placa não é branca na imagem

Embora o refil seja fisicamente branco, **a câmera não o registra como
branco**. As lâmpadas BL UVA emitem radiação UV-A acompanhada de faixa visível
violeta-azulada, e uma superfície branca reflete o que recebe.

Três fatores tornam a cor registrada imprevisível:

| Fator | Efeito |
|---|---|
| Dominante violeta-azulado | A placa aparece azulada ou violácea, não branca |
| **Fluorescência** | Adesivos e papéis costumam conter branqueadores ópticos, que emitem luz visível sob UV — a superfície pode aparecer mais clara e saturada do que sob luz comum |
| **Balanço de branco automático** | A câmera tenta compensar o dominante; o resultado varia conforme o modelo do equipamento e o conteúdo do quadro |
| Luz ambiente concorrente | A iluminação do estabelecimento se mistura à UV em proporção variável ao longo do dia |

### Consequência para o modelo

**A cor absoluta não pode ser usada como característica.** Um modelo que
aprenda "placa é a região branca" falhará sistematicamente.

O que permanece **relativamente** estável é a relação de luminância: a placa é
mais clara que os insetos, qualquer que seja o dominante de cor.

Essa estabilidade tem um limite importante — o contraste diminui conforme a
placa amarela. Ver seção 4.2.

### Exigências

| Exigência | Detalhe |
|---|---|
| Dataset sintético | Variação agressiva de dominante de cor e temperatura, cobrindo desde forte dominante violeta até imagem corrigida pelo balanço de branco |
| Augmentation | Jitter de matiz, saturação e balanço de canais durante o treino |
| Baseline | Opera sobre o canal V (luminosidade) do HSV, não sobre matiz — escolha que já o torna tolerante ao dominante de cor |

### Recomendação para a instalação

Fixar o balanço de branco da câmera, em vez de deixá-lo automático. Uma cor
consistentemente deslocada é preferível a uma cor que varia de forma
imprevisível entre capturas: o modelo aprende a lidar com viés constante, mas
não com viés aleatório.

Registrado como pendência de especificação da câmera em
`../foundation/hardware_armadilha.md`.

## 4.2 Amarelamento do adesivo

O adesivo exposto continuamente a luz UV amarela de forma progressiva. Um refil
com 40 dias de uso **não é mais branco**, e a câmera registra essa mudança.

O amarelamento produz dois problemas distintos, que exigem mitigações
diferentes.

### 4.2.1 Perda de contraste sob iluminação UV

Uma superfície amarela **absorve comprimentos de onda curtos** — exatamente a
faixa violeta-azulada emitida pelas lâmpadas BL UVA. Conforme o adesivo
amarela, ele passa a absorver a luz que o ilumina.

O efeito não é apenas um deslocamento de matiz: é uma **redução de
luminância**. A placa fica progressivamente mais escura sob essa iluminação
específica.

Um segundo fator atua na mesma direção: os branqueadores ópticos que fazem o
adesivo novo fluorescer também se degradam com a exposição a UV. Um refil
velho perde o brilho fluorescente que tinha quando novo.

**Consequência:** o contraste entre placa e insetos **diminui ao longo da vida
do refil**. A discriminação fica mais difícil justamente nos refis próximos da
saturação — que são os que importam para a decisão de troca.

| Afetado | Impacto |
|---|---|
| Dataset sintético | Deve modelar a progressão de tom **e de luminância**, não apenas a mudança de cor |
| Modelo treinado | Precisa de exemplos com contraste reduzido, sob pena de degradar em refis antigos |
| Baseline por limiar fixo | Degrada de forma previsível — ver seção 9.2 |

Esse comportamento é derivado das propriedades da iluminação e do material, e
**deve ser confirmado com fotos reais** de refis em diferentes idades.

### 4.2.2 Risco de correlação espúria

Amarelamento e percentual de cobertura crescem juntos ao longo do ciclo do
refil — ambos são função do tempo de exposição.

Se no dataset sintético o tom amarelado aparecer sempre acompanhado de alta
cobertura, o modelo pode aprender a **inferir cobertura a partir da cor de
fundo**, em vez de detectar insetos. Ele acertaria no conjunto de teste
sintético e falharia de forma inexplicável em campo — por exemplo, num refil
antigo de ambiente com pouca infestação.

**Mitigação obrigatória:** variar tom e luminância da placa de forma
**estatisticamente independente** do percentual de cobertura. O dataset precisa
conter placas amareladas com pouca cobertura e placas novas com muita.

As duas mitigações são complementares: a primeira garante que o modelo veja
contraste reduzido, a segunda garante que ele não use o tom como atalho.

---

# 5. Cálculo do percentual

```text
area_placa    = pixels(placa_limpa) + pixels(placa_coberta)
area_coberta  = pixels(placa_coberta)

percentual_coberto = (area_coberta / area_placa) × 100
```

## 5.1 Regras

| Regra | Definição |
|---|---|
| Arredondamento | Duas casas decimais, compatível com `numeric(5,2)` do banco |
| `area_placa` igual a zero | Erro de inferência — o modelo não localizou a placa. Retorna `500`, não persiste |
| Área mínima de placa | Se `area_placa` for menor que 5% dos pixels da imagem, tratar como falha de detecção |
| Pixels de `fundo` | Nunca entram no cálculo, nem no numerador nem no denominador |

O limite mínimo de 5% existe para capturar o caso em que o modelo produz
ruído disperso em vez de localizar a placa. Sem essa verificação, uma detecção
falha produziria um percentual aparentemente válido, calculado sobre uma área
que não é a placa.

## 5.2 Derivação do status

Aplicada sobre `percentual_coberto`, conforme
`../foundation/project_overview.md`, seção 7.2:

```text
percentual < 40           → "ok"
40 <= percentual <= 70    → "atencao"
percentual > 70           → "trocar"
```

Os limiares são constantes de configuração, não valores fixos no código —
serão recalibrados com dados reais.

**Grafia:** o valor persistido e trafegado pela API é `atencao`, sem acento. A
acentuação é aplicada apenas na exibição, pelo frontend.

---

# 6. Pré-processamento

Sequência exata aplicada a toda imagem antes da inferência:

| Ordem | Operação | Parâmetro |
|---|---|---|
| 1 | Conversão de espaço de cor | Para RGB, descartando canal alfa se houver |
| 2 | Redimensionamento | 768 × 576 pixels, interpolação bilinear |
| 3 | Normalização | Média e desvio-padrão do ImageNet |

**Valores de normalização** (obrigatórios por causa do encoder pré-treinado):

```text
media  = [0.485, 0.456, 0.406]
desvio = [0.229, 0.224, 0.225]
```

## 6.1 Sobre a resolução

768 × 576 mantém proporção 4:3, compatível com o enquadramento típico de
câmera, e ambas as dimensões são divisíveis por 32 — requisito da U-Net, que
reduz a resolução cinco vezes.

O dimensionamento considera o objeto de interesse: um mosquito de
aproximadamente 5 mm sobre um refil de 450 mm ocupa cerca de 8 pixels nessa
resolução. Abaixo disso a segmentação perde a capacidade de distinguir
indivíduos próximos.

Resoluções maiores melhoram o detalhe, mas aumentam tempo de inferência e
consumo de memória. Este valor pode ser revisto após a primeira avaliação de
métricas, e a alteração exige retreino.

**Distorção de proporção:** o redimensionamento não preserva a proporção
original da foto. Isso é aceitável porque o percentual é uma razão entre áreas
segmentadas — a distorção afeta numerador e denominador igualmente.

---

# 7. Pós-processamento

| Ordem | Operação |
|---|---|
| 1 | `argmax` sobre o eixo de classes, produzindo mapa de rótulos |
| 2 | Contagem de pixels por classe |
| 3 | Cálculo do percentual conforme seção 3 |
| 4 | Geração da imagem de máscara sobreposta |

## 7.1 Máscara sobreposta

Imagem gerada e persistida no momento da análise, servida por
`GET /api/analises/{id}/mascara`.

| Propriedade | Valor |
|---|---|
| Base | Imagem original, na resolução em que foi enviada |
| Sobreposição | Apenas pixels da classe `placa_coberta` |
| Cor | Magenta, `#FF00FF` |
| Opacidade | 40% |
| Formato | PNG |

Magenta foi escolhido por ser uma cor saturada, ausente da cena real — a placa
é branca e os insetos são escuros e acinzentados. Qualquer tom neutro se
confundiria com o próprio conteúdo da imagem; magenta é inequivocamente uma
marcação do sistema, e não algo presente na armadilha.

A máscara é gerada uma vez e armazenada, não recalculada a cada visualização —
a tela de detalhe exibe várias miniaturas simultaneamente.

---

# 8. Carregamento dos pesos

| Item | Definição |
|---|---|
| Origem | Variável de ambiente `MODEL_WEIGHTS_PATH` |
| Valor padrão | `/app/models/checkpoints/latest.pt` |
| Momento | Na inicialização da aplicação, não sob demanda |
| Arquivo ausente | Falha imediata na inicialização, com mensagem explícita |
| Arquivo inválido | Falha imediata na inicialização |

A falha na inicialização é deliberada. Se o carregamento fosse adiado até a
primeira requisição, a aplicação subiria aparentemente saudável e só revelaria
o problema quando alguém tentasse analisar uma imagem — provavelmente durante
a apresentação.

## 8.1 Composição de `modelo_versao`

Formato `semver+hash`, conforme `../data/data_model.md`, seção 7.2.

| Parte | Origem |
|---|---|
| `semver` | Variável de ambiente `MODEL_VERSION`, ex.: `v1.2.0` |
| `hash` | Oito primeiros caracteres do SHA-256 do arquivo de pesos |

O hash é calculado uma vez, na inicialização, e mantido em memória. Resultado:
`v1.2.0+a3f9c2e1`.

---

# 9. Baseline OpenCV

Implementação clássica para comparação, conforme
`../foundation/tech_stack.md`, seção 4.2.

| Item | Definição |
|---|---|
| Método | Limiar de luminosidade — canal V do espaço HSV |
| Entrada | Mesma imagem pré-processada da seção 4 |
| Saída | Mesmo formato do modelo — percentual e status |
| Execução | Offline, em notebook de avaliação |

O baseline **não é exposto pela API**. Serve à comparação metodológica no
relatório, não ao uso operacional.

## 9.1 Método

Como o refil é branco e os insetos são escuros, a separação por luminosidade é
direta: pixels abaixo de um limiar de brilho são considerados cobertos.

O limiar é calibrado sobre o conjunto de treino, não escolhido arbitrariamente
— usar um valor arbitrário tornaria a comparação injusta com o modelo
treinado.

## 9.2 Limitações conhecidas e esperadas

O baseline apresenta duas limitações estruturais, ambas decorrentes de operar
apenas sobre luminosidade.

### Não delimita a placa

A moldura da armadilha também é branca, e o limiar de brilho não distingue uma
superfície branca da outra. Consequências:

- exige que a imagem esteja previamente recortada na placa;
- não reproduz a segmentação em três classes;
- sob variação de iluminação, sombras na moldura são contadas como área
  coberta.

### Não distingue inseto de sujeira

Conforme a definição da seção 3, apenas insetos contam como área coberta.
Um limiar de brilho classifica **qualquer** região escura como coberta,
incluindo poeira e manchas.

O baseline, portanto, **superestima sistematicamente** o percentual em
superfícies sujas. O erro cresce com o tempo de exposição do refil, justamente
quando a decisão de troca se torna crítica.

### O limiar fixo perde validade com o tempo

Esta é a limitação mais grave, e decorre da perda de contraste descrita na
seção 4.2.1.

Um limiar de luminosidade calibrado em refis novos assume determinada
diferença de brilho entre placa e insetos. Conforme a placa amarela e escurece
sob a luz UV, essa diferença encolhe — e o mesmo limiar passa a classificar
região de placa como coberta.

O resultado é uma **superestimação crescente ao longo do ciclo do refil**, que
se soma ao erro por sujeira. Ambos os erros apontam na mesma direção e ambos
crescem com o tempo.

Um limiar adaptativo — calculado por imagem, em vez de fixo — mitigaria
parcialmente o problema. **Não deve ser implementado.** O baseline existe para
representar a abordagem clássica ingênua; torná-lo adaptativo aproximaria seu
comportamento do modelo treinado e enfraqueceria a comparação.

A limitação deve ser **medida em função da idade do refil** e reportada.

### Interpretação

Ambas as limitações **não são defeitos de implementação — são o resultado
esperado**, e constituem o argumento a favor do modelo treinado. Devem ser
medidas e reportadas, não contornadas.

Ajustar o baseline até que supere as próprias limitações descaracterizaria a
comparação: exigiria incorporar análise de forma e contexto, que é exatamente
o que o modelo treinado faz.

---

# 10. Contrato de inferência

Interface que o pipeline expõe ao backend:

```text
Entrada:  imagem (arquivo)
Saída:    percentual_coberto  (float, 0.00 a 100.00)
          status              ("ok" | "atencao" | "trocar")
          modelo_versao       (str, formato semver+hash)
          mascara             (imagem PNG)
```

Em qualquer falha, a inferência levanta exceção — nunca retorna resultado
parcial ou valor padrão. O tratamento é responsabilidade do endpoint, conforme
`../api/api_spec.md`, seção 6.1.

---

# 11. Pendências

- [ ] Revisar resolução de entrada após a primeira avaliação de métricas

---

# FIM DO MODELO E INFERÊNCIA
