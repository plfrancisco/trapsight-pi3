# CURRENT TASK — DADOS DE DEMONSTRAÇÃO — Projeto Integrador

**Versão:** 1.0
**Status:** ATIVA
**Escopo:** script de seed com os seis cenários de demonstração

---

# 1. Objetivo

Popular o banco com histórico realista, viabilizando a demonstração das
telas centrais (projeção de saturação, timelapse, painel de alertas) sem
esperar meses de uso real acumulado.

---

# 2. Escopo

Cobre apenas o script de seed. Não cobre o gerador de dataset sintético em
si (`current_task_modelo.md`, ML02), do qual esta task depende para as
imagens.

---

# 3. Tarefas

## SEED01 — Script de seed

- [ ] Seis armadilhas (`ARM-001` a `ARM-006`) cobrindo os estados descritos
      na especificação: em alerta, projeção com taxa constante, refil novo,
      histórico com dois refis anteriores, sem análises, sem refil ativo
- [ ] Determinístico (semente fixa), idempotente
- [ ] Datas relativas à execução, nunca absolutas
- [ ] Reexecução remove apenas os dados criados pelo próprio seed antes de
      recriar
- [ ] Imagens geradas correspondem ao percentual registrado em cada análise

**Especificação:** `../plan/data/seed_demo.md`.
**Dependências:** `completed/current_task_banco.md` (DB01), `current_task_modelo.md`
(ML02).

**Nota:** a correspondência entre imagem e percentual é obrigatória. Se as
imagens forem aleatórias, o timelapse mostra uma placa que não bate com a
curva do gráfico — na tela que deveria provar que o modelo funciona.

---

# 4. Critério de conclusão

Rodar o script popula o banco com os seis cenários, cada um demonstrando
corretamente o comportamento de interface especificado para aquele estado.

---

# FIM DA TASK — DADOS DE DEMONSTRAÇÃO
