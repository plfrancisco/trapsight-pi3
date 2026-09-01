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
| Percentual atual | Aproximadamente 78% |
| Cruzou o limiar de 70% | 3 dias atrás |

Produz alerta ativo há 3 dias no painel do dashboard.

## 3.2 `ARM-002` — Projeção

| Item | Valor |
|---|---|
| Refil instalado | 20 dias atrás |
| Análises | 7, a cada 3 dias |
| Percentual atual | Aproximadamente 55% |
| Taxa | Constante, cerca de 2,75 pp por dia |

Com taxa constante, a projeção resulta em aproximadamente 5 dias até
saturar — valor verificável manualmente durante a demonstração.

## 3.3 `ARM-003` — Refil novo

| Item | Valor |
|---|---|
| Refil instalado | 6 dias atrás |
| Análises | 2 |
| Percentual atual | Aproximadamente 12% |

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
| Ambiente | Bloqueado fora de desenvolvimento |
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
