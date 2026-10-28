# CURRENT TASK — DEPENDÊNCIAS EXTERNAS — Projeto Integrador

**Versão:** 1.0
**Status:** CONCLUÍDA
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

**Estado (2026-10-26):** EXT01, EXT02 e EXT03 confirmadas como concluídas pelo usuário.
Em EXT04 a escolha feita foi Vercel e Supabase (`../../../deploy/vercel-supabase.md`), e não
um servidor próprio com domínio e firewall do provedor, como os itens abaixo pressupõem;
os demais itens de EXT04 foram resolvidos em 2026-10-28 (ver abaixo). `../../plan/foundation/project_overview.md`
(seção 9) ainda registra integrantes e prazo como "a definir".

## EXT01 — Material da empresa parceira

- [x] Fotos reais de armadilhas em diferentes níveis de saturação
- [x] Fotos de refis em idades diferentes (confirma a perda de contraste por
  amarelamento — `../../plan/model/modelo_spec.md`, seção 4.2.1)
- [x] Confirmar se o adesivo apresenta fluorescência sob as lâmpadas UV
- [x] Especificação da câmera, se/quando a Fase 2 for iniciada

**Especificação:** `../../plan/foundation/hardware_armadilha.md`, seção 5;
`../../plan/data/dataset_sintetico.md`, seção 8.
**Contato:** Gustavo — ver `../../plan/foundation/stakeholder_evidencias.md`.

**Concluída em:** 2026-10-28, por decisão do usuário: sem domínio comprado nem
VPS paga.

**Impacto se atrasar:** bloqueia a calibração do gerador sintético e o
critério de aprovação no teste real (`avaliacao_spec.md`). Quanto mais tarde
chegar, menor a chance de corrigir o gerador a tempo.

## EXT02 — Entrevista estruturada com o Gustavo

- [x] Frequência atual de troca, custo por deslocamento, custo do refil,
  volume mensal de trocas antecipadas
- [x] Validar persona e jornada do usuário (hoje marcadas como hipótese no
  diagnóstico)
- [x] Confirmar se o nome da empresa pode ser citado no relatório final

**Especificação:** `../../plan/foundation/stakeholder_evidencias.md`, seção 5.
**Dependências:** nenhuma — pode ser feita a qualquer momento.

## EXT03 — Integrantes e prazo

- [x] Confirmar integrantes do grupo e RAs
- [x] Definir divisão de responsabilidades por trilha (infra, banco, api,
  frontend, modelo)
- [x] Definir prazo final de entrega e marcos intermediários

**Especificação:** `../../plan/foundation/project_overview.md`, seção 9
(restrições).
**Dependências:** nenhuma.

**Nota:** sem isso, nenhuma outra task tem responsável nem prazo — é o item
de menor esforço e maior efeito destravante do projeto.

## EXT04 — Provedor de hospedagem e domínio

- [x] Escolher o provedor do servidor (VPS ou equivalente, com firewall de rede
  do provedor que negue tudo por padrão)
- [x] Registrar um domínio e apontar o DNS (necessário ao HTTPS automático) —
  dispensado: não haverá domínio comprado; a publicação usa o endereço da
  Vercel, com HTTPS da plataforma
- [x] Definir quem administra o servidor, o acesso por SSH com chave e onde
  ficam os backups do banco — concluído; não haverá servidor próprio (Vercel e
  Supabase), e os backups seguem `../../../deploy/backup-restauracao.md`
- [x] Definir o orçamento mensal aceitável — concluído: sem VPS paga nem domínio
  comprado, o projeto usa só os planos gratuitos

**Especificação:** `../../plan/foundation/login.md`, seções 10.1 e 10.5.
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
