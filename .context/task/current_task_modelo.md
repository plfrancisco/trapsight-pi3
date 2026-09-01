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
obtenção de material da empresa parceira (`current_task_externo.md`).

---

# 3. Tarefas

## ML01 — Especificar o pipeline de treino

- [ ] Documento definindo função de perda, tratamento do desbalanceamento
      de classes, otimizador, taxa de aprendizado, tamanho de lote, número
      de épocas, parada antecipada e parâmetros de augmentation
- [ ] Publicado em `../plan/model/` e referenciado no índice de planejamento

**Especificação:** ainda não existe — este é o único documento de
arquitetura pendente no projeto. Contexto de stack em
`../plan/foundation/tech_stack.md`, seção 4.

**Dependências:** nenhuma.

**Ponto crítico a resolver na especificação:** numa placa com 10% de
cobertura, `placa_coberta` é minoria absoluta dos pixels. Uma CrossEntropy
simples seria dominada pelas classes majoritárias — o modelo aprenderia a
prever "não coberto" em quase tudo, com boa acurácia de pixel e nenhuma
utilidade real. A especificação precisa tratar isso explicitamente (perda
ponderada, Dice loss, ou combinação).

## ML02 — Gerador de dataset sintético

- [ ] Implementar conforme `dataset_sintetico.md` — sprites, fundo, composição
      por união de silhuetas, distratores, metadados
- [ ] Verificar os critérios de aceite da seção 9 do documento (correlação
      idade × cobertura próxima de zero, reprodutibilidade por semente)

**Especificação:** `../plan/data/dataset_sintetico.md`.
**Dependências:** nenhuma.

## ML03 — Baseline OpenCV

- [ ] Segmentação por limiar de luminosidade (canal V do HSV)
- [ ] Limiar calibrado sobre o conjunto de treino, não escolhido
      arbitrariamente
- [ ] **Não implementar limiar adaptativo**

**Especificação:** `../plan/model/modelo_spec.md`, seção 9.
**Dependências:** ML02 (precisa de imagens para calibrar).

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
**Dependências:** ML01, ML02.

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

- [ ] Pipeline real segue `modelo_spec.md`, seções 6 a 8 (pré-processamento,
      pós-processamento, carregamento de pesos)
- [ ] Contrato de entrada/saída idêntico ao do stub — nenhum outro ponto do
      backend muda
- [ ] Falha de inicialização (pesos ausentes/inválidos) impede a aplicação
      de subir

**Especificação:** `../plan/model/modelo_spec.md`, seções 6 a 10.
**Dependências:** ML04, `completed/current_task_api.md` (API04).

---

# 4. Dependência externa

Esta trilha não depende de material da empresa parceira para **rodar** — o
dataset sintético é suficiente para validar o pipeline tecnicamente. Mas a
**calibração** (`dataset_sintetico.md`, seção 8) e a validação do critério
de aprovação no teste real (`avaliacao_spec.md`) dependem do material
descrito em `current_task_externo.md` (EXT01).

Um primeiro treino sem essa calibração é aceitável como teste de fumaça do
pipeline — não deve ser tratado como resultado final.

---

# 5. Ordem de execução

ML01 e ML02 em paralelo → ML03 (depende de ML02) → ML04 (depende de ML01 e
ML02) → ML05 → ML06 → ML07.

---

# 6. Critério de conclusão

Modelo treinado substituindo o stub, com avaliação completa reportada
conforme `avaliacao_spec.md`, incluindo a comparação com o baseline sob
sujeira e idade simulada.

---

# FIM DA TASK — MODELO E ML
