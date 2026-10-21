# CURRENT TASK — DEPENDÊNCIAS EXTERNAS — Projeto Integrador

**Versão:** 1.0
**Status:** ATIVA
**Escopo:** itens que dependem da empresa parceira, do grupo ou da faculdade
— não são executáveis por código

---

# 1. Objetivo

Consolidar em um único lugar as pendências que não avançam sozinhas por
trabalho técnico — dependem de resposta de terceiros. Isso evita que fiquem
espalhadas e esquecidas nos documentos de especificação.

---

# 2. Escopo

Esta task não tem "implementação" no sentido de código. Cada item é uma
ação de comunicação ou decisão de grupo.

---

# 3. Tarefas

## EXT01 — Material da empresa parceira

- [ ] Fotos reais de armadilhas em diferentes níveis de saturação
- [ ] Fotos de refis em idades diferentes (confirma a perda de contraste por
      amarelamento — `../plan/model/modelo_spec.md`, seção 4.2.1)
- [ ] Confirmar se o adesivo apresenta fluorescência sob as lâmpadas UV
- [ ] Especificação da câmera, se/quando a Fase 2 for iniciada

**Especificação:** `../plan/foundation/hardware_armadilha.md`, seção 5;
`../plan/data/dataset_sintetico.md`, seção 8.
**Contato:** Gustavo — ver `../plan/foundation/stakeholder_evidencias.md`.

**Impacto se atrasar:** bloqueia a calibração do gerador sintético e o
critério de aprovação no teste real (`avaliacao_spec.md`). Quanto mais tarde
chegar, menor a chance de corrigir o gerador a tempo.

## EXT02 — Entrevista estruturada com o Gustavo

- [ ] Frequência atual de troca, custo por deslocamento, custo do refil,
      volume mensal de trocas antecipadas
- [ ] Validar persona e jornada do usuário (hoje marcadas como hipótese no
      diagnóstico)
- [ ] Confirmar se o nome da empresa pode ser citado no relatório final

**Especificação:** `../plan/foundation/stakeholder_evidencias.md`, seção 5.
**Dependências:** nenhuma — pode ser feita a qualquer momento.

## EXT03 — Integrantes e prazo

- [ ] Confirmar integrantes do grupo e RAs
- [ ] Definir divisão de responsabilidades por trilha (infra, banco, api,
      frontend, modelo)
- [ ] Definir prazo final de entrega e marcos intermediários

**Especificação:** `../plan/foundation/project_overview.md`, seção 9
(restrições).
**Dependências:** nenhuma.

**Nota:** sem isso, nenhuma outra task tem responsável nem prazo — é o item
de menor esforço e maior efeito destravante do projeto.

## EXT04 — Provedor de hospedagem e domínio

- [ ] Escolher o provedor do servidor (VPS ou equivalente, com firewall de rede
      do provedor que negue tudo por padrão)
- [ ] Registrar um domínio e apontar o DNS (necessário ao HTTPS automático)
- [ ] Definir quem administra o servidor, o acesso por SSH com chave e onde
      ficam os backups do banco
- [ ] Definir o orçamento mensal aceitável

**Especificação:** `../plan/foundation/login.md`, seções 10.1 e 10.5.
**Dependências:** nenhuma — pode ser feita a qualquer momento.

**Impacto se atrasar:** bloqueia HOST02 e HOST03 de `current_task_autenticacao_hospedagem.md`
(o proxy precisa do domínio para emitir o certificado). A implementação do login
e a suíte local não dependem disso.

---

# 4. Critério de conclusão

Cada item marcado é uma resposta obtida, não uma ação de código. A task se
encerra quando os quatro itens estiverem resolvidos ou explicitamente adiados
por decisão do grupo.

---

# FIM DA TASK — DEPENDÊNCIAS EXTERNAS
