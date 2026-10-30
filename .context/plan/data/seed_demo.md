# DADOS DE DEMONSTRAÇÃO — Projeto Integrador

**Versão:** 1.0
**Status:** ATIVO
**Escopo:** script de seed que popula o banco com histórico para a
apresentação

---

# 1. Objetivo

Especificar a carga de dados que permite demonstrar o sistema.

Sem ela a apresentação é inviável. As telas centrais — projeção de saturação,
timelapse e painel de alertas — dependem de histórico acumulado ao longo de
semanas. Em uma instalação limpa não há nada para exibir, e não é possível
gerar esse histórico ao vivo.

---

# 2. Princípios

| Princípio | Definição |
|---|---|
| Determinístico | Semente fixa; execuções repetidas produzem o mesmo resultado |
| Idempotente | Executar mais de uma vez não duplica registros |
| Isolado | Nunca executa automaticamente; exige comando explícito |
| Datado relativamente | Datas calculadas a partir da data de execução, não fixas |

O uso de datas relativas é o que impede a demonstração de envelhecer: uma
análise gravada com data absoluta apareceria como "há oito meses" na
apresentação, quebrando a projeção de saturação, que depende de dados
recentes.

---

# 3. Cenários

Seis armadilhas, cada uma cobrindo um estado distinto da interface. O conjunto
foi desenhado para que **toda tela e todo caso de exceção especificados
tenham representação**.

Os percentuais dos cenários foram escritos para os limiares de 40% e 70% e
reescalados por 20/70 (2/7) para os limiares do produto, 10% e 20%, com duas
casas decimais. A razão é a mesma dos limiares, então a forma de cada série e
os **dias até saturar não mudam** (ARM-001 já saturado, ARM-002 em 5 dias e o
refil ativo de ARM-004 em 26 dias). Todos os alvos ficam abaixo do teto de 35%
de cobertura do gerador.

| Cenário | Dias de uso | Percentuais após a escala 2/7 (%) |
|---|---|---|
| ARM-001 | 2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32 | 2,86; 4,86; 6,86; 8,86; 10,86; 12,86; 14,86; 16,57; 18,29; 20,71; 22,29 |
| ARM-002 | 2, 5, 8, 11, 14, 17, 20 | 1,57; 3,93; 6,29; 8,64; 11,00; 13,36; 15,71 |
| ARM-003 | 3, 6 | 2,00; 3,43 |
| ARM-004, refil 1 | 3, 18, 33 | 4,00; 11,43; 18,57 |
| ARM-004, refil 2 | 3, 18, 33, 42 | 3,43; 9,14; 15,71; 19,43 |
| ARM-004, refil 3 | 3, 6, 9, 12, 15 | 2,29; 3,43; 5,14; 6,29; 7,71 |

ARM-005 e ARM-006 não têm leituras. A escala preserva a relação com o limiar
de troca de 20% definido no produto; o limiar de atenção permanece em 10%.

| # | Identificador | Estado | Demonstra |
|---|---|---|---|
| 1 | `ARM-001` | Em alerta | Painel de alertas e status `trocar` |
| 2 | `ARM-002` | Atenção, taxa constante | Projeção de dias até saturar |
| 3 | `ARM-003` | Refil novo | Estado saudável, poucas análises |
| 4 | `ARM-004` | Histórico com dois refis anteriores | Timelapse completo e padrão de dente de serra |
| 5 | `ARM-005` | Sem análises | Estado vazio no dashboard |
| 6 | `ARM-006` | Sem refil ativo | Bloqueio de nova análise |

## 3.1 `ARM-001` — Em alerta

| Item | Valor |
|---|---|
| Refil instalado | 32 dias atrás |
| Análises | 11, a cada 3 dias |
| Percentual atual | Aproximadamente 22% |
| Cruzou o limiar de 20% | 3 dias atrás |

Produz alerta ativo há 3 dias no painel do dashboard.

## 3.2 `ARM-002` — Projeção

| Item | Valor |
|---|---|
| Refil instalado | 20 dias atrás |
| Análises | 7, a cada 3 dias |
| Percentual atual | Aproximadamente 16% |
| Taxa | Constante, cerca de 0,8 pp por dia |

Com taxa constante, a projeção resulta em aproximadamente 5 dias até
chegar ao limiar de troca (20%) — valor verificável manualmente durante a
demonstração.

## 3.3 `ARM-003` — Refil novo

| Item | Valor |
|---|---|
| Refil instalado | 6 dias atrás |
| Análises | 2 |
| Percentual atual | Aproximadamente 3% |

Estado saudável com projeção já disponível, por haver duas análises.

## 3.4 `ARM-004` — Histórico completo

| Item | Valor |
|---|---|
| Refis anteriores | 2, encerrados após 38 e 45 dias |
| Refil ativo | Instalado 15 dias atrás |
| Análises | Distribuídas pelos três refis |

É a armadilha usada para demonstrar o timelapse em modo de histórico
completo. A curva sobe até a troca, cai bruscamente e volta a subir,
evidenciando os ciclos.

Os ciclos anteriores terminam perto do limiar de troca (cerca de 19%) e o
refil ativo, aos 15 dias, está por volta de 8%, com taxas médias parecidas
entre os ciclos (entre 0,4 e 0,5 pp por dia).

Os refis anteriores devem ter durações diferentes — refis idênticos sugeririam
dados fabricados de forma pouco cuidadosa.

## 3.5 `ARM-005` — Sem análises

Armadilha e refil ativo cadastrados, nenhuma análise registrada.

Demonstra o comportamento definido em `../frontend/telas_spec.md`, seção 4.1:
exibida sem percentual e sem projeção.

## 3.6 `ARM-006` — Sem refil ativo

Armadilha cadastrada, refil anterior encerrado, nenhum refil ativo.

Demonstra o bloqueio de nova análise e o erro `REFIL_ATIVO_INEXISTENTE`
definido em `../api/api_spec.md`, seção 2.3.

---

# 4. Imagens

Cada análise do seed exige uma imagem e a máscara correspondente.

| Item | Definição |
|---|---|
| Origem | Gerador de dataset sintético |
| Correspondência | O percentual real da imagem deve corresponder ao percentual registrado na análise |
| Local | `data/uploads/`, conforme `data_model.md`, seção 7.1 |

A correspondência entre imagem e percentual registrado é obrigatória. Se as
imagens forem aleatórias, o timelapse exibirá uma placa que não corresponde à
curva do gráfico — e a incoerência fica visível na apresentação, exatamente na
tela que deveria comprovar que o modelo funciona.

**Dependência:** este seed só pode ser implementado após o gerador de dataset
sintético. Ver seção 6.

---

# 5. Execução

| Item | Definição |
|---|---|
| Comando | Script dedicado, executado manualmente |
| Ambiente | Fora de desenvolvimento ou em banco remoto, exige `--confirmar-ambiente` |
| Reexecução | Remove os dados de seed anteriores antes de recriar |
| Escopo da limpeza | Apenas registros criados pelo próprio seed |

A limpeza restrita aos registros do seed evita que uma reexecução apague dados
inseridos manualmente durante os testes.

---

# 6. Dependências

| Depende de | Motivo |
|---|---|
| Migration inicial | As tabelas precisam existir |
| Gerador de dataset sintético | Fornece as imagens com percentual conhecido |

A segunda dependência define a ordem de implementação: o seed vem depois do
gerador, não antes.

---

# 7. Pendências

Nenhuma pendência de decisão.

---

# FIM DOS DADOS DE DEMONSTRAÇÃO
