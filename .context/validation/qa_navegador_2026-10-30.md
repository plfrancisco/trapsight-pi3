# QA no navegador — TrapSight (2026-10-30)

Somente observação: nenhum código, spec, teste, `.env` ou compose foi alterado; nada foi commitado.

## 1. Resumo

| Item | Valor |
|---|---|
| Data | 2026-10-29 (noite, UTC-3) a 2026-10-30 |
| Commit (`git rev-parse HEAD`) | `85bec476dc2e50a56432128172c6df3ea763a144` (branch `dev`; working tree com `backend/.dockerignore` e arquivos de `backend/training/treino/` modificados por outros agentes) |
| Navegador | Navegador embutido do app Claude (pane), com scripts JS na página para preencher campos e anexar arquivos. Capturas em `qa_evidencias/` |
| Ambiente | `trapsight-dev-db-1` (Postgres 17), `qa-backend` (`localhost:8000`), `trapsight-dev-frontend-1` (Vite, `localhost:5173`). Sempre por `localhost` |
| Inferência | **`INFERENCE_MODE=stub`**: toda análise devolve 55,00 % e versão `v0.1.0-dev+00000000` (`backend/src/inference/stub.py`) |
| Armazenamento de imagens | `STORAGE_BACKEND=database` |
| Contas | Gerente `qa-gerente@example.test` (conta da sessão anterior, senha redefinida pela CLI), operador `qa-operador2@example.test` (CLI) e `qa-operador3@example.test` (criado pela UI). Senhas só em arquivo fora do repositório, nunca impressas |
| Seed | Executado (ver seção 5): 6 armadilhas, 8 refis, 32 análises |

Observação: já existia um gerente no banco; por isso não foi possível criar um gerente novo e a senha da conta antiga foi redefinida pela CLI.

## 2. Resultados

| ID | Descrição | Resultado | Evidência |
|---|---|---|---|
| A1 | `/armadilhas/nova` sem sessão vai a `/login` e volta ao destino após entrar | PASS | observado por `history.state.destino` e retorno à rota |
| A2 | Login inválido: mensagem única "E-mail ou senha inválidos." (e-mail inexistente e conta existente com senha errada) | PASS | `A2_login_invalido_email_inexistente.jpg` |
| A3 | Login válido; nada de token/senha em `localStorage`/`sessionStorage`; `document.cookie` vazio; cookie `HttpOnly; SameSite=strict; Path=/`, sem `Secure` e sem `Expires`/`Max-Age` (dev) | PASS | atributos lidos do `Set-Cookie` via curl (o painel não tem DevTools de Cookies) |
| A4 | Logout leva ao login; voltar no histórico não mostra conteúdo; cookie antigo recebe 401 no servidor | PASS | verificado por JS e curl |
| A5 | Rotas de dados sem sessão: 401; sessão revogada no meio do uso: volta ao login com "Sua sessão expirou. Entre novamente.", 1 única requisição, sem laço | PASS | contagem de requisições |
| A6 | Senha com caractere invisível: **política ACEITA** (ZWSP e U+FEFF ao final); o login funciona com os caracteres exatos | PASS (informativo: aceita) | CLI `criar-usuario` |
| A7 | `/conta/senha`: erros por código sem eco da senha (atual errada, sequência trivial, contém e-mail, contém `trapsight`, igual à atual, confirmação diferente, curta); sucesso revoga outras sessões e invalida a senha antiga | PASS | verificado por JS e curl |
| B1 | Gerente vê Contas; cria operador; e-mail duplicado (inclusive caixa diferente) e senha fraca dão mensagens por código; sucesso limpa os campos e atualiza a lista, sem exibir a senha | PASS | `B1_tela_contas_gerente.jpg`, `B1_conta_criada.jpg` |
| B2 | Operador criado pela UI é levado a `/conta/senha` com o motivo; outras rotas redirecionam; API devolve 403 `TROCA_DE_SENHA_OBRIGATORIA`; `/me` funciona | PASS | curl + UI |
| B3 | Operador não vê Contas; `/contas` mostra "Acesso negado" sem chamar `/api/usuarios`; API: 403 `ACESSO_NEGADO` em GET e POST | PASS | `B3_operador_acesso_negado_contas.jpg` |
| B4 | Segundo gerente: API rejeita `papel` (422 `VALIDACAO_FALHOU`); CLI recusa criar e promover ("Já existe um gerente") | PASS | saída da CLI |
| C1 | Cadastro: identificador obrigatório, só espaços rejeitado, duplicado com mensagem, 300 caracteres rejeitado pela API | PASS (ver nota L1) | `C1_identificador_duplicado.jpg`, `C1_campos_longos_erro_generico.jpg` |
| C2 | Lista, detalhe, edição (`data_instalacao` bloqueada) e remoção lógica (some da lista) | PASS | JS |
| C3 | Catálogo: StickFly K-45 disponível e selecionado no cadastro | PASS | `C3_cadastro_modelo_stickfly.jpg` |
| D1 | Nova análise com JPG e PNG válidos: percentual, status e versão do modelo exibidos; **a máscara não aparece ao lado da original** | **FAIL** | `D1_resultado_analise_stub_sem_mascara.jpg` |
| D2 | Arquivos inválidos (texto com extensão .jpg, vazio, 11 MB, 300×300, GIF, PNG 22 Mpx): mensagem clara, sem travar | PASS | JS |
| D2b | Limite de upload na UI e na API é de 4 MB, a spec diz 10 MB | **FAIL** | `backend/src/services/upload.py:11` |
| D3a | Status coerente com 10 %/20 % nos valores do seed: 22,41 % trocar, 15,89 % atenção, 7,84 % e 3,56 % ok | PASS | dashboard |
| D3b | Valores exatamente em 10,00 % e 20,00 % e status via upload | NÃO EXECUTADO | o stub fixa 55 % |
| D4 | Troca de refil: confirmação, refil antigo encerrado, novo ativo, série reinicia; análise em armadilha sem refil bloqueada na UI e 409 `REFIL_ATIVO_INEXISTENTE` na API | PASS | UI + curl |
| D4b | `dias_em_uso` de refil criado "hoje" aparece como 1 dia (spec mostra 0) | **FAIL** | API `GET /api/armadilhas` |
| D5 | Gráfico de evolução, histórico só do refil ativo, "Refis anteriores"; imagem e máscara dão 401 sem sessão e 200 com sessão | PASS | `D5_detalhe_armadilha_ciclo_atual.jpg` |
| D5b | Timelapse (reprodução, velocidade, marcador, modo "histórico completo", máscara por quadro) **ausente** | **FAIL** | `D5_grafico_sem_timelapse_texto_70pct.jpg` |
| D5c | Cartão do gráfico diz "Estimativa ao atingir **70 %**" (limiar do produto é 20 %) | **FAIL** | mesma captura |
| E1 | Painel de alertas: contagem, lista com "Em alerta há N dias", link ao detalhe; ordenação trocar → menos dias; estados "sem refil ativo", "sem análises" e "sem estimativa" | PASS | `E1_dashboard_miniatura_modelo_estatica.jpg` |
| E1b | Miniatura dos cards é uma imagem estática do modelo (inclusive para armadilhas sem análise), não a foto mais recente | **FAIL** | mesma captura |
| E2 | Seis cenários do seed: ARM-001 trocar 22,41 %, ARM-002 atenção 4 dias, ARM-003 ok 34 dias (2 análises), ARM-004 ok 26 dias com 2 refis anteriores, ARM-005 sem análises, ARM-006 sem refil | PASS | JS + API |
| F1 | Backend parado: "Não foi possível conectar à API." e botão "Tentar novamente"; dashboard com "—" | PASS | `F1_backend_fora_erro_conexao.jpg` |
| F2 | 375 e 768 px: sem rolagem horizontal em dashboard, análise, detalhe, cadastro, senha e 404; barra inferior em 375 | PASS | `F2_dashboard_375px.jpg` |
| F2b | 1280 px | NÃO EXECUTADO | a sessão foi interrompida antes da medição |
| F2c | Em ~1024 px, "Instalado em" e "Dias em uso" se sobrepõem no cartão "Ciclo atual" | **FAIL** | `F2_detalhe_sobreposicao_campos_1024.jpg` |
| F3 | Tema claro e escuro funcionam e persistem | PASS | `F3_tema_escuro_dashboard.jpg` |
| F4 | Tab com foco visível (outline 2,4 px), link de pular conteúdo, todos os campos com rótulo (o campo oculto `usuario` é `display:none`), `autocomplete` correto (`username`, `current-password`, `new-password`) | PASS | JS |
| F5 | Console só com 1 × 401 esperado (`/auth/me` antes do login); nenhuma resposta 5xx; nenhum segredo no código-fonte do frontend (bundle de dev) | PASS (ver nota L2) | console e rede |
| F6 | Rota inexistente mostra "Página não encontrada"; id inexistente mostra "Armadilha não encontrada" | PASS | JS |

Contagem: PASS 26 · FAIL 7 · NÃO EXECUTADO 2.

## 3. Falhas

**D5b — Timelapse ausente (alta).**
- Passos: entrar como gerente, abrir o detalhe de ARM-001 ou ARM-004 (≥ 2 análises).
- Esperado (`telas_spec.md` 4.2.1 e 8.5): botão de reprodução, velocidade 200–2000 ms, marcador arrastável, alternância "Refil ativo / Histórico completo" e foto com máscara a cada quadro.
- Observado: só gráfico e um quadro com a foto original. Não há botões de reprodução nem de escopo. Os componentes `ControlesTimelapse` e `QuadroTimelapse` existem, mas `Timelapse.tsx` não os usa. O dente de serra do histórico completo não pode ser mostrado.

**D1 — Máscara não aparece (média).**
- Passos: Nova análise, escolher ARM-QA1, enviar `valida_800x600.jpg`.
- Esperado (`telas_spec.md` 4.3 e 8.3): original e máscara lado a lado.
- Observado: apenas "Imagem original". `GET /api/analises/{id}/mascara` devolve 200 com PNG.

**E1b — Miniaturas estáticas (média).**
- Esperado (`telas_spec.md` 4.1 e 8.4): miniatura da foto mais recente; sem análise, informar que não há imagem, sem foto ilustrativa.
- Observado: todos os 9 cards usam `/src/assets/modelos/stickfly-k45.webp`.

**D5c — Texto "70 %" (média).**
- Esperado (`project_overview.md` 7.2, `telas_spec.md` 5): limiar de troca de 20 %.
- Observado: `frontend/src/components/EvolucaoGrafico.tsx:167` fixa "Estimativa ao atingir 70% de cobertura", ao lado de uma linha de referência em 20 %.

**D2b — Limite de upload (média).**
- Esperado (`api_spec.md` 2.4): 10 MB, com 413 `ARQUIVO_MUITO_GRANDE` acima disso.
- Observado: 4 MB na UI ("até 4 MB") e na API. Um PNG de 22 Mpx e poucos KB também recebe "A imagem excede o limite de 4 MB", o que engana.

**D4b — `dias_em_uso` (baixa).**
- Passos: registrar a troca de refil às 22h locais (01h UTC).
- Esperado (`api_spec.md` 5.1): `dias_em_uso: 0` no refil novo.
- Observado: 1. O front envia a data local (29/10) e o servidor conta a partir da data UTC (30/10).

**F2c — Sobreposição de campos (baixa).** Em ~1024 px, no detalhe, "27/09/2026" colide com "33 dias".

## 4. Não executado
- D3b: o stub devolve sempre 55 %; os limites exatos de 10 % e 20 % exigem inferência real ou dados inseridos direto no banco.
- F2b (1280 px): interrompido.
- Verificação dos atributos do cookie nas ferramentas do navegador (aba Application): o painel não as oferece; os atributos foram lidos do cabeçalho `Set-Cookie`.
- Itens do checklist manual da seção 9 de `seguranca_testes.md` ligados a produção: HTTPS, `__Host-`, Compose de produção e varredura de portas.
- Teste de XSS em "modelo": o campo vem de catálogo fechado. Identificador e localização com `<img src=x onerror=alert(1)>` foram exibidos como texto no dashboard, no detalhe e no seletor, sem executar (0 alertas).
- Leitura dos arquivos de `.context/rules/` e de `login.md` seções 1–4: os arquivos de regras foram só varridos; o restante foi lido.

## 5. Divergências de ambiente
- `backend/.env` está com `LIMIAR_ATENCAO=40` e `LIMIAR_TROCAR=70` (padrão do produto: 10/20). O `qa-backend` usa 10/20 por `-e`. Sem essa variável, o backend estaria com os limiares antigos. O `.env` não foi editado.
- Inferência em `stub` (55 % constante), sem pesos em `models/checkpoints`.
- O banco não estava vazio: já existiam contas da sessão anterior. Uma delas (`qa-gerente@example.test`) foi reaproveitada, com a senha redefinida pela CLI.
- **Seed:** o commit `85bec47` registra a convergência (ML02C) e os testes do seed passando em Windows e Linux. Por isso o seed foi rodado **dentro do `qa-backend`**: `pip install opencv-python-headless` dentro do contêiner, catálogo copiado para `/tmp/dados` do contêiner e `python -m src.seed_demo`. Resultado: "6 armadilhas, 8 refis e 32 análises". O manifesto `.seed_demo_manifest.json` foi para `data/uploads/`, que o `.gitignore` ignora. O repositório não foi modificado.
- **`qa_migrador` NÃO foi removido:** `DROP ROLE qa_migrador` falha porque o papel é dono das tabelas `alembic_version`, `armadilha`, `refil` e `analise`. Removê-lo exigiria `REASSIGN OWNED`, que muda a propriedade dos objetos, e não foi feito sem autorização. O papel continua como superusuário no banco local.
- O cabeçalho de resposta `server: uvicorn` está presente (dev; `login.md` 9.5 pede removê-lo só em produção).
- Dois contêineres reiniciaram durante a sessão (queda da sessão do agente); os dados permaneceram.
- O prompt cita `/alterar-senha`; a rota real e a da spec é `/conta/senha`.

## 6. Logs do backend (e-mails, ids e IPs redigidos)
Contagem dos eventos `auth.*`, sem erros 5xx nem `Traceback`:
```
7 auth.login_falhou
3 auth.sessao_revogada motivo=limite
2 auth.acesso_negado
1 auth.troca_senha_recusada motivo=senha_atual
1 auth.troca_senha_recusada motivo=igual_atual
1 auth.senha_trocada
2 auth.logout
N auth.login_ok (sem senha, hash ou token)
```
CLI: `cli_criar_usuario_falha` (segundo gerente), `cli_definir_papel_falha` (promoção), `cli_criar_usuario_sucesso` (operadores e contas de teste) e `cli_redefinir_senha_sucesso`.

## Notas menores
- L1: o erro de 300 caracteres no cadastro é o genérico "A requisição contém campos inválidos.", sem apontar o campo. A identificação é por maiúsculas e minúsculas (`arm-qa1` e `ARM-QA1` coexistem); a spec não define.
- L2: o código-fonte do frontend não contém segredos. Esta verificação não cobre o bundle de produção.
- O breadcrumb da página 404 mostra "Nova armadilha".
- Detalhe de ARM-006 (sem refil): mostra o rótulo "Refil ativo" e o link "Enviar a primeira imagem", embora a análise esteja bloqueada.
- Com troca de senha pendente, o menu lateral continua visível (as rotas redirecionam).
- Armadilha removida: `GET /api/armadilhas/{id}` ainda responde 200 com `removida_em`.
