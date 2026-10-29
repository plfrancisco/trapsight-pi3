# CURRENT TASK — MODELO E ML — Projeto Integrador

**Versão:** 1.0
**Status:** ATIVA
**Escopo:** especificação de treino, gerador de dataset, baseline, treino
da U-Net, avaliação e substituição do stub de inferência

---

# 1. Objetivo

Produzir o modelo de segmentação treinado que substitui o stub de inferência
usado pela API, junto com o baseline clássico para comparação e a avaliação
que sustenta a aprovação do MVP.

---

# 2. Escopo

Esta é a trilha com mais dependência externa do projeto — ver seção 4.
Cobre da especificação de treino (ainda não escrita) até a substituição do
stub. Não cobre a Fase 2 (fine-tuning com dados reais), que só começa após
obtenção de material da empresa parceira (`completed/current_task_externo.md`).

---

# 3. Tarefas

## ML01 — Especificar o pipeline de treino

- [x] Documento definindo função de perda, tratamento do desbalanceamento
      de classes, otimizador, taxa de aprendizado, tamanho de lote, número
      de épocas, parada antecipada e parâmetros de augmentation
- [x] Publicado em `../plan/model/` e referenciado no índice de planejamento

**Especificação:** `../plan/model/treino_spec.md`. Contexto de stack em
`../plan/foundation/tech_stack.md`, seção 4.

**Dependências:** nenhuma.

**Ponto crítico a resolver na especificação:** numa placa com 10% de
cobertura, `placa_coberta` é minoria absoluta dos pixels. Uma CrossEntropy
simples seria dominada pelas classes majoritárias — o modelo aprenderia a
prever "não coberto" em quase tudo, com boa acurácia de pixel e nenhuma
utilidade real. A especificação precisa tratar isso explicitamente (perda
ponderada, Dice loss, ou combinação).

## ML02 — Gerador de dataset sintético

- [x] Implementar conforme `dataset_sintetico.md` — sprites, fundo, composição
      por união de silhuetas, distratores, metadados
- [x] Verificar os critérios de aceite da seção 9 do documento (correlação
      idade × cobertura próxima de zero, reprodutibilidade por semente)

**Especificação:** `../plan/data/dataset_sintetico.md`.
**Dependências:** nenhuma.
**Concluída em:** 2026-10-21.

## ML02A — Banco de sprites de insetos

- [x] Fonte do MVP: **fotos de insetos brasileiros com licença aberta**
      (iNaturalist, observações com `quality_grade=research`, Brasil,
      licenças CC0, CC-BY e CC-BY-NC), recortadas com segmentador pronto;
      conjuntos do Roboflow Universe só entram se trouxerem máscara e forem
      de insetos presentes no Brasil
- [x] Grupos cobertos: moscas (doméstica, varejeira, drosófila), mosquitos
      (*Culex*, *Aedes*), formigas, baratas, mariposas e besouros pequenos;
      cada sprite grava o `grupo` no manifesto
- [x] A **licença e o autor de cada foto** ficam registrados no manifesto;
      descartar qualquer foto sem licença que permita uso acadêmico (CC-ND e
      "todos os direitos reservados" ficam fora)
- [x] Script de preparo em `backend/training/` que lê o conjunto baixado,
      recorta cada inseto pela máscara fornecida e grava PNG com canal alfa
- [x] `manifest.json` no formato do README do gerador (`arquivo`, `categoria`,
      `fonte`, `licenca`, `especie`, `fragmentado`), com as três categorias de
      tamanho e fragmentos de inseto
- [x] Limiar de qualidade do recorte: descartar sprites vazios, minúsculos ou
      com bordas serrilhadas, e registrar quantos foram descartados e por quê
- [x] Mínimo de 300 sprites válidos no banco final, distribuídos entre as
      categorias, para a composição não repetir sempre os mesmos insetos
- [x] Banco e conjuntos baixados ficam **fora do repositório** (caminho
      configurável); a chave de API do Roboflow vem de variável de ambiente e
      nunca é gravada em arquivo versionado
- [x] Inspeção visual de uma amostra do dataset gerado com o banco real
      (máscara de três classes, distratores fora da máscara) e relatório com
      as imagens da amostra

**Especificação:** `../plan/data/dataset_sintetico.md`, seções 3 e 9.
**Dependências:** ML02.
**Concluída em:** 2026-10-21.

**Nota:** o uso de `rembg` (grupo opcional de dependências de treino, fora das
dependências da API) está **aprovado** para o MVP, porque não há fotos reais do
parceiro (EXT01) nem conjunto brasileiro com máscara. A qualidade do recorte é
garantida pelo limiar de qualidade, não pela confiança no segmentador: o que
falhar é descartado. Quando as fotos reais chegarem, o banco é refeito com elas.
O custo é de tempo de máquina (download e processamento local); não consome
tokens de IA.

## ML02B — Dataset por recomposição de insetos reais

- [x] Extrair cada inseto real das placas fotografadas pela própria máscara e
      recompô-lo sobre outra placa real ou sobre base sintética StickFly K-45,
      sem ajuste de cor nem de brilho
- [x] Reservar placas para avaliação (14 das 69) com guarda em tempo de
      execução que impede o uso de qualquer recorte ou base de avaliação
- [x] Amostra de 30 imagens gerada e conferida: 29 dos 30 alvos de cobertura
      atingidos, correlação entre idade e cobertura de 0,048
- [x] Completar o rótulo das 6 placas usadas como base: hoje 142 das 456
      manchas escuras visíveis (31,1%) estão em `placa_coberta`; meta acima de
      90%, e o que continuar ambíguo vai para uma classe ignorada pela perda,
      nunca para `placa_limpa`. Atendido pelo método v5 (SAM nos originais em
      alta resolução): o ambíguo vai para a classe 255, em 0,13–0,98% da área
      das bases elegíveis; a B117 (1,56%) foi excluída como base
- [x] Particionar treino, validação e teste **por placa base** e pela placa de
      origem dos recortes, com guarda em tempo de execução; hoje a divisão é
      por índice da amostra e uma mesma base aparece em dois conjuntos
- [x] Calibrar a cobertura contra a referência das placas reais (300 colagens:
      20,38% contra 14,38%; 900: 40,99% contra 34,65%; 2.200: 57,28%, com só
      2.036 posicionadas, contra 62,62%) e fazer o acúmulo variar de forma
      contínua, sem ilhas de borda nítida
- [x] Gerar o dataset definitivo e conferir os critérios da seção 9 da
      especificação

**Especificação:** `../plan/data/dataset_sintetico.md`, seções 5.4, 7 e 9.
**Dependências:** ML02, ML02A e as máscaras das placas reais geradas por
`backend/training/teste_real_ums.py`.

**Estado (2026-10-28):** concluída. Dataset v5 de 3.000 imagens em
`dataset/recomposicao-real-v5-3000-20261027` (2.100/450/450), com os critérios
P, L, D, C, T, K, R e I aceitos em `relatorio-validacao.json`. Limitações
registradas em `../plan/data/dataset_sintetico.md`: 3/1/1 bases reais por
conjunto, referência de espalhamento da faixa 4–8% com só 4 placas e rótulo
incompleto nas 14 placas de avaliação.

## ML02C — Convergência do gerador em Linux

- [ ] Identificar por que a imagem de `ARM-001` não converge para o alvo de
      31,00% de cobertura em Linux (medido 26,38%, tolerância de 2,0 pp),
      comparando a cobertura da máscara antes e depois de `_finalizar_cena`
      nas duas plataformas
- [ ] Os 10 testes de `backend/tests/seed_demo/` passam em Linux, no CI

**Especificação:** `../plan/data/dataset_sintetico.md`, seção 5.3.
**Dependências:** ML02.

**Estado (2026-10-23):** em Linux, num checkout limpo, 329 testes passam e esses
10 falham, todos com a mesma mensagem; no Windows passam. A causa raiz não foi
determinada. A suíte de backend rodou em Linux pela primeira vez no CI de
2026-10-22.

## ML03 — Baseline OpenCV

- [x] Segmentação por limiar de luminosidade (canal V do HSV)
- [x] Limiar calibrado sobre o conjunto de treino, não escolhido
      arbitrariamente
- [x] **Não implementar limiar adaptativo**
- [x] Recalibrar o limiar sobre o dataset por recomposição (ML02B), com a classe
      255 ignorada (fora da placa, do percentual e das métricas)

**Especificação:** `../plan/model/modelo_spec.md`, seção 9.
**Dependências:** ML02 e ML02A (precisa de imagens para calibrar).

**Calibração (2026-10-28, dataset v5):** `../../backend/training/baseline_calibracao.json`,
versão 2, limiar V = 217, Dice de treino 0,81733856, 2.100 amostras de treino.

| Conjunto | Amostras | Dice | IoU | Erro médio (pp) | Acurácia de status |
|---|---:|---:|---:|---:|---:|
| Validação | 450 | 0,6790 | 0,5140 | 13,81 | 0,5422 |
| Teste | 450 | 0,8352 | 0,7171 | 3,34 | 0,7267 |
| Teste, base sintética | 223 | 0,8554 | 0,7473 | 2,56 | 0,8386 |
| Teste, base real | 227 | 0,8216 | 0,6972 | 4,10 | 0,6167 |

Na validação, as 232 amostras de base real (uma única placa, B310) têm Dice 0,5709
e erro de 24,27 pp, contra 0,8833 e 2,69 pp nas 218 de base sintética. Os valores
anteriores (Dice 0,8055 em 450 amostras de teste) eram do dataset sintético
descartado e não valem mais. As métricas por conjunto ficam em
`metricas_baseline_{validacao,teste}.json`, dentro do dataset (não versionado).

**Nota:** o baseline existe para representar a abordagem clássica ingênua.
Torná-lo adaptativo aproximaria seu comportamento do modelo treinado e
enfraqueceria a comparação — ver seção 9.2 da especificação.

## ML04 — Pipeline de treino da U-Net

- [ ] Treino em PyTorch puro (sem Lightning), usando
      `segmentation_models_pytorch` com encoder ResNet34 pré-treinado
- [ ] Registrar semente global, sementes de geração, hiperparâmetros,
      versões de bibliotecas e `modelo_versao` resultante
- [ ] Divisão 70/15/15 do conjunto sintético **por semente de geração**, sem
      reuso entre conjuntos

**Especificação:** ML01 (pipeline de treino); divisão dos conjuntos em
`../plan/model/avaliacao_spec.md`, seção 2.
**Dependências:** ML01, ML02, ML02A, ML02B.

**Estado (2026-10-22):** o pipeline está implementado em `backend/training/treino/`
com testes em CPU. Falta o teste de fumaça E0 na GPU, que falhou por falta de
memória de vídeo na escolha do lote por passo; a ML04 só é marcada quando o E0
passar (`../plan/model/treino_spec.md`, seção 8).

**Estado (2026-10-26):** a execução dos treinos ficou para o fim, depois de a
aplicação estar completa; o E0 segue pendente e nenhum checkpoint existe. Pontos
a resolver antes dele:

- a escolha automática do lote em `backend/training/treino/loop.py` devolve 1
  mesmo quando nem esse lote cabe, sem avisar; o treino então falha com a
  mensagem de memória insuficiente, que manda reduzir o lote, e não há saída
  quando ele já é 1;
- a máquina de treino não está definida; a de desenvolvimento tem uma RTX 3050
  de 6 GB;
- o `pyproject.toml` resolve `torch` pelo índice `cu128` no Windows, e essa build
  não traz kernels para GPUs Pascal, como a GTX 1050 Ti (4 GB):
  https://dev-discuss.pytorch.org/t/cuda-toolkit-version-and-architecture-support-update-maxwell-and-pascal-architecture-support-removed-in-cuda-12-8-and-12-9-builds/3128
- depende de ML02B: os defeitos de rótulo e de divisão precisam estar corrigidos
  antes de qualquer treino que valha como resultado.

## ML05 — Avaliação e métricas comparativas

- [ ] Reportar Dice/IoU por classe, erro percentual absoluto, acurácia e
      matriz de confusão do status
- [ ] Comparar modelo vs. baseline nos subconjuntos de iluminação/ângulo,
      sujeira e amarelamento
- [ ] Reportar erro **por idade do refil**, não apenas média agregada
- [ ] Conferir os critérios de aprovação da seção 4.1, com tolerância zero
      para `trocar` classificado como `ok`

**Especificação:** `../plan/model/avaliacao_spec.md`.
**Dependências:** ML03, ML04.

## ML06 — Baseline OpenCV — comparação obrigatória sob sujeira e idade

- [ ] Subconjunto de teste com refis simulando sujeira acumulada
- [ ] Subconjunto de teste com refis de diferentes idades simuladas
- [ ] Gráfico erro × idade, duas curvas (modelo e baseline)

**Especificação:** `../plan/model/avaliacao_spec.md`, seção 5.
**Dependências:** ML05.

## ML07 — Substituir stub pela inferência real

- [x] Pipeline real segue `modelo_spec.md`, seções 6 a 8 (pré-processamento,
      pós-processamento, carregamento de pesos)
- [x] Contrato de entrada/saída idêntico ao do stub — nenhum outro ponto do
      backend muda
- [x] Falha de inicialização (pesos ausentes/inválidos) impede a aplicação
      de subir

**Especificação:** `../plan/model/modelo_spec.md`, seções 6 a 10.
**Dependências:** ML04, `completed/current_task_api.md` (API04).
**Concluída em:** 2026-10-22.

**Nota:** implementada e validada com pesos sintéticos de teste, em
`backend/tests/inference/test_inference_modelo.py` e no teste de integração pela
API; nenhum checkpoint treinado existe ainda, então o desempenho real depende
de ML04. O modo padrão é `modelo` e a aplicação não sobe sem pesos;
`INFERENCE_MODE=stub` mantém o stub no desenvolvimento local.

---

# 4. Dependência externa

Esta trilha não depende de material da empresa parceira para **rodar** — o
dataset sintético é suficiente para validar o pipeline tecnicamente. Mas a
**calibração** (`dataset_sintetico.md`, seção 8) e a validação do critério
de aprovação no teste real (`avaliacao_spec.md`) dependem do material
descrito em `completed/current_task_externo.md` (EXT01).

Um primeiro treino sem essa calibração é aceitável como teste de fumaça do
pipeline — não deve ser tratado como resultado final.

---

# 5. Ordem de execução

ML01 e ML02 em paralelo → ML02A → ML02B → ML03 (depende de ML02) → ML04 (depende
de ML01 e ML02B) → ML05 → ML06. A ML02C corre em paralelo e a ML07 foi
antecipada, com o contrato do stub preservado.

---

# 6. Critério de conclusão

Modelo treinado substituindo o stub, com avaliação completa reportada
conforme `avaliacao_spec.md`, incluindo a comparação com o baseline sob
sujeira e idade simulada.

---

# FIM DA TASK — MODELO E ML
