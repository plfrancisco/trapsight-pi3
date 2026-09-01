# HARDWARE DA ARMADILHA — StickFly K-45

**Versão:** 1.0
**Status:** ATIVO
**Escopo:** especificações do equipamento real e implicações para a visão
computacional

---

# 1. Objetivo

Registrar as especificações do equipamento da empresa parceira e derivar as
implicações técnicas para a geração do dataset sintético, o posicionamento da
câmera e o pré-processamento das imagens.

---

# 2. Especificações técnicas

| Item | Especificação |
|---|---|
| Modelo | StickFly K-45 |
| Dimensões (C × A × L) | 50 cm × 27 cm × 22 cm |
| Material do corpo | Aço com pintura epóxi branca / aço inox / ABS de alta resistência |
| Instalação | Parede |
| Lâmpadas | 3× 15 W BL UVA |
| **Refil adesivo** | **450 × 220 mm** |
| Voltagem | 110 V ou 220 V (chave seletora) |
| Consumo | 0,045 kW/h |
| Cobertura | 60 m² |
| Peso | 4,280 kg |

---

# 3. Implicações para a visão computacional

## 3.1 Superfície de interesse

O objeto a ser analisado é o **refil adesivo de 450 × 220 mm**, não a
armadilha inteira. A razão de aspecto é de aproximadamente **2,05:1**, o que
orienta:

- as dimensões das imagens sintéticas geradas;
- o crop ou retificação da imagem real antes de entrar no modelo;
- a resolução de entrada da rede — manter proporção próxima evita distorção.

## 3.2 Área física por pixel

Como as dimensões do refil são conhecidas, é possível converter percentual de
área coberta em **área física real** (cm² cobertos), caso isso seja útil para
o relatório ou para calibrar o limiar de troca.

## 3.3 Iluminação

As três lâmpadas BL UVA de 15 W ficam próximas à superfície adesiva. Isso
implica:

- iluminação artificial constante e dominante sobre a placa;
- **dominante violeta-azulado nas imagens** — lâmpadas BL UVA emitem UV-A com
  faixa visível violeta, e a superfície reflete o que recebe;
- possível fluorescência do adesivo, caso contenha branqueadores ópticos;
- risco de reflexo ou brilho especular na superfície;
- gradiente de iluminação, por serem fontes pontuais e próximas;
- mistura com a luz própria do estabelecimento, em proporção variável.

**Consequência crítica: a placa não é registrada como branca pela câmera.**
Apesar de ser fisicamente branca, a cor na imagem depende do dominante UV, da
fluorescência, do balanço de branco da câmera e da luz ambiente concorrente.

O modelo não pode usar cor absoluta como característica — apenas a relação de
luminância entre placa e insetos é estável. Análise completa em
`../model/modelo_spec.md`, seção 4.1.

Essas condições devem ser reproduzidas na geração do dataset sintético e na
augmentation.

## 3.4 Instalação em parede

A armadilha é fixa em parede, o que significa:

- ângulo de captura da câmera é fixo e previsível por instalação;
- a distorção de perspectiva tende a ser constante para uma mesma unidade;
- há variação entre instalações diferentes (altura, distância da câmera), o
  que a augmentation deve cobrir.

## 3.5 Cor do refil e do corpo

**O refil adesivo é branco.** O corpo da armadilha também é branco, em pintura
epóxi, ou aço inox.

### Consequência favorável

O contraste entre insetos (escuros) e a superfície (branca) é o máximo
possível. Isso beneficia tanto o modelo treinado quanto o baseline OpenCV,
que pode operar por limiar de luminosidade em vez de matiz.

### Consequência desfavorável — risco técnico

**A placa é branca e a moldura ao redor também é branca.**

Isso afeta diretamente a segmentação em três classes definida em
`../model/modelo_spec.md`, seção 2. Duas das três classes — `fundo`, que
inclui a moldura, e `placa_limpa` — têm praticamente a mesma cor. O modelo não
pode separá-las por cor; precisa aprender pela **geometria e pelo contexto
espacial**: a placa é o retângulo interno, a moldura o que a circunda.

Uma U-Net consegue aprender isso, pois seu campo receptivo captura contexto
amplo. Mas é um aprendizado mais difícil do que seria com cores distintas, e
tem duas implicações obrigatórias:

| Implicação | Detalhe |
|---|---|
| Dataset sintético | Deve incluir a moldura branca ao redor da placa, com variação de proporção e enquadramento. Sem isso o modelo nunca aprende a distinguir |
| Verificação de área mínima | A regra de 5% definida em `../model/modelo_spec.md`, seção 5.1, ganha importância — ela é o que detecta o caso em que o modelo confunde moldura com placa |

### Sujeira acumulada

Superfícies brancas evidenciam poeira e resíduo, o que cria um segundo desafio
de discriminação.

**Sujeira sem inseto não conta como área coberta** — decisão registrada em
`../model/modelo_spec.md`, seção 3. A métrica mede capacidade de captura, não
estado estético da superfície.

Isso significa que o modelo precisa separar duas coisas visualmente parecidas:
insetos e sujeira são, ambos, manchas escuras sobre branco. A distinção depende
de forma e textura.

**Implicação obrigatória para o dataset sintético:** as imagens geradas devem
incluir sujeira como distrator — visível na imagem, ausente da máscara. Sem
exemplos negativos, o modelo aprenderá que toda mancha escura é inseto e
falhará em qualquer foto real de refil com algum tempo de uso.

---

# 4. Câmera de captura

## 4.1 Escopo

Câmera fixa operando 24/7 em campo está **fora do escopo do MVP** (ver
`project_overview.md`, seção 5.2). As fotos reais necessárias agora —
diferentes níveis de saturação, diferentes idades de refil — devem ser
capturadas com celular comum, com exposição e foco travados manualmente
(modo Pro / AE-AF lock). Não há necessidade de comprar hardware para isso.

## 4.2 Candidata para a Fase 2 (referência, não implementação)

Para a eventual câmera fixa de produção, o candidato de referência é o
**ESP32-CAM**: módulo com câmera e microcontrolador WiFi integrados,
programável, baixo custo (~R$ 40–60).

| Requisito | Como o ESP32-CAM atende |
|---|---|
| Balanço de branco fixo (seção 3.3) | Configurável via firmware — parâmetro exposto na API da câmera (OV2640), ao contrário de câmeras de consumo com AWB automático não configurável |
| Exposição fixa | Igualmente configurável via firmware, mesma justificativa |
| Captura periódica/sob demanda | Fácil de programar (temporizador ou requisição HTTP) |
| Custo | Compatível com escala de instalação em múltiplas armadilhas |

**Alternativas descartadas para este fim:** câmeras de vigilância disfarçada
(ex.: modelos "mini spy cam" tipo A9) — feitas para gravação curta e oculta,
não para operação fixa e configurável; batería pequena, sem controle de
exposição/balanço de branco, ângulo de visão não documentado.

Esta seção é **referência para planejamento futuro**, não uma decisão de
compra ou implementação do MVP atual.

---

# 5. Pendências

- [ ] Obter fotos reais do equipamento em uso, em diferentes níveis de
      saturação
- [ ] Confirmar se o adesivo apresenta fluorescência sob as lâmpadas UV
- [ ] **Obter fotos de refis em idades diferentes** — necessário para confirmar
      a perda de contraste por amarelamento descrita em
      `../model/modelo_spec.md`, seção 4.2.1

**Confirmado:** a placa fica exposta, sem grade, tela ou painel frontal
obstruindo a superfície.

**Confirmado:** o refil é liso, sem marcações, logotipo ou bordas impressas.
Elimina o risco de viés sistemático na segmentação (mancha escura fixa,
presente mesmo em refil novo, sendo confundida com inseto). O distrator fixo
descrito anteriormente não se aplica — os distratores relevantes continuam
sendo os variáveis: sujeira, teia, pelos e respingos (ver
`../model/modelo_spec.md`, seção 3.2).

---

# FIM DO HARDWARE DA ARMADILHA
