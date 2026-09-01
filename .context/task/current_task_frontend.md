# CURRENT TASK — FRONTEND — Projeto Integrador

**Versão:** 1.0
**Status:** ATIVA
**Escopo:** interface web — as 4 telas definidas em `telas_spec.md`

---

# 1. Objetivo

Implementar a interface de demonstração: dashboard com painel de alertas,
detalhe da armadilha com gráfico e timelapse, nova análise, e cadastro.

---

# 2. Escopo

Cobre as 4 telas do MVP. Não cobre a tela de comparação com o baseline
(explicitamente fora de escopo, `telas_spec.md`, seção 6) nem autenticação.

---

# 3. Tarefas

## FE01 — Setup do projeto

- [x] Vite + React + TypeScript + Tailwind configurados
- [x] `VITE_API_URL` lido de variável de ambiente

**Especificação:** `../plan/foundation/tech_stack.md`, seção 3.
**Dependências:** `completed/current_task_infra.md` (INFRA02).
**Concluída em:** 2026-10-08.

## FE02 — Camada de serviços da API

- [ ] Funções cobrindo os 8 endpoints de `api_spec.md`
- [ ] Dados da API mantidos em `snake_case`, sem conversão para camelCase

**Especificação:** `../plan/api/api_spec.md`; `../plan/frontend/telas_spec.md`,
seção 8.5.
**Dependências:** FE01.

**Nota:** código próprio do frontend (fora da API) segue `camelCase`
normalmente — a exceção é só nos dados vindos da API.

## FE03 — Dashboard

- [ ] Lista de armadilhas ordenada por urgência (`trocar` primeiro, depois
      menor `dias_ate_saturar`)
- [ ] Painel de alertas no topo, com contagem e lista de casos em `trocar`
- [ ] Estados de exceção: sem armadilhas, sem refil ativo, sem análises

**Especificação:** `../plan/frontend/telas_spec.md`, seções 4.1 e 6.
**Dependências:** FE02, `completed/current_task_api.md` (API03).

## FE04 — Detalhe da armadilha

- [ ] Dados da armadilha e do refil ativo
- [ ] Gráfico de evolução do percentual (Recharts)
- [ ] Lista de análises com miniatura, data, percentual e status
- [ ] Botão "Registrar troca de refil"

**Especificação:** `../plan/frontend/telas_spec.md`, seção 4.2.
**Dependências:** FE02.

## FE05 — Timelapse

- [ ] Reprodução automática sincronizada com marcador no gráfico
- [ ] Arrastar o marcador pausa a reprodução
- [ ] Alterna entre modo "refil ativo" e "histórico completo"
- [ ] Oculto com menos de duas análises

**Especificação:** `../plan/frontend/telas_spec.md`, seção 4.2.1.
**Dependências:** FE04.

## FE06 — Nova análise

- [ ] Fluxo: seleciona armadilha, envia imagem, exibe resultado
- [ ] Resultado mostra imagem original e máscara lado a lado, percentual,
      status e versão do modelo
- [ ] Bloqueia envio se armadilha sem refil ativo

**Especificação:** `../plan/frontend/telas_spec.md`, seção 4.3.
**Dependências:** FE02, `completed/current_task_api.md` (API07).

## FE07 — Cadastro de armadilha

- [ ] Formulário: identificador, modelo, localização, data de instalação
- [ ] Ao criar, oferece criação imediata do primeiro refil

**Especificação:** `../plan/frontend/telas_spec.md`, seção 4.4.
**Dependências:** FE02.

---

# 4. Ordem de execução

FE01 → FE02 → (FE03, FE04, FE07 em paralelo) → FE05 (depende de FE04) e
FE06 (depende do endpoint de análise estar pronto).

---

# 5. Critério de conclusão

As 4 telas funcionam contra a API real (mesmo com stub de inferência),
incluindo todos os estados de exceção documentados em `telas_spec.md`.

---

# FIM DA TASK — FRONTEND
