# CURRENT TASK — PWA E CÂMERA NO CELULAR — Projeto Integrador

**Versão:** 1.0
**Status:** PROPOSTA (aguarda a confirmação das decisões da seção 4 antes de implementar)
**Escopo:** tornar o TrapSight instalável como PWA e permitir enviar a foto direto da câmera do celular

---

# 1. Objetivo

Permitir que o gerente ou o operador instale o TrapSight na tela inicial do celular (Android e iOS), abra o aplicativo em tela cheia e fotografe a armadilha direto da câmera, sem tocar nas regras de negócio, na API nem no modelo.

---

# 2. Escopo

Cobre o manifesto, os ícones, o *service worker* do "casco" do aplicativo, os ajustes de publicação na Vercel e o envio de foto pela câmera. **Não cobre** funcionamento offline da análise (o modelo roda no servidor), fila de envio offline, notificações *push* nem publicação em lojas de aplicativos.

Fatos do código em 05/11/2026 que moldam a task:

- `frontend/index.html` não tem `link rel="manifest"`, ícone da Apple nem `theme-color` por tema (há um único `#f8faf8`).
- Não existe `frontend/public/`; os ativos ficam em `frontend/src/assets/`. Manifesto, `sw.js` e ícones precisam de caminhos fixos na raiz, então ficam em `frontend/public/`.
- Cores do tema: claro `#f5f7f6` (fundo) e `#0a5c66` (primária); escuro `#0a1316` (fundo) e `#2fd6a1` (primária).
- O `vercel.json` reescreve `/(.*)` para `/index.html` no serviço do frontend. Arquivos reais têm precedência, mas é preciso conferir `sw.js` e o manifesto.
- A API limita o upload a **4 MB** e **20 milhões de pixels**; fotos de câmera de celular costumam passar de 4 MB, e as de 48 MP passam do limite de pixels.
- O logo de referência está em `.context/reference/marca/trapsight-logo-referencia.png` (pasta local, fora do Git).

---

# 3. Tarefas

## PWA01 — Manifesto, ícones e metadados

- [ ] `frontend/public/manifest.webmanifest` com `name`, `short_name`, `lang` pt-BR, `start_url` e `scope` em `/`, `display` standalone, `theme_color` `#0a5c66` e `background_color` `#f5f7f6`
- [ ] Ícones PNG de 192 e 512 px, um 512 px *maskable* e o ícone da Apple de 180 px, gerados do logo de referência, em `frontend/public/icons/`
- [ ] `index.html` com `link rel="manifest"`, `apple-touch-icon` e `theme-color` com `media` para o tema claro e o escuro
- [ ] Teste automatizado: o manifesto é JSON válido, tem os campos obrigatórios e todos os ícones citados existem

**Especificação:** `../plan/frontend/telas_spec.md` (seção de acesso e navegação).
**Dependências:** nenhuma.
**Estimativa:** 1 hora.

## PWA02 — Service worker do casco (nunca a API)

- [ ] `frontend/public/sw.js` com cache `trapsight-casco-v1`
- [ ] Navegação: rede primeiro, com queda para o `index.html` em cache quando não houver conexão
- [ ] `/assets/*` (nomes com hash, imutáveis): cache primeiro
- [ ] **Qualquer `/api/*`, método diferente de GET e outra origem: direto pela rede, sem nunca gravar em cache** (as respostas trazem fotos e dados de contas)
- [ ] `activate` apaga caches de versões antigas
- [ ] Aviso discreto de "sem conexão" quando o casco abre offline: "A análise precisa de internet"
- [ ] Registro em `main.tsx` somente em produção e quando houver suporte; a versão nova assume na próxima navegação
- [ ] Testes: uma requisição `/api` nunca chama `cache.put`; um POST não é interceptado; o registro não ocorre em desenvolvimento

**Especificação:** `../rules/security_spec.md` (nenhum dado autenticado em cache do navegador).
**Dependências:** PWA01.
**Estimativa:** 2 a 3 horas.

## PWA03 — Publicação na Vercel e segurança

- [ ] `vercel.json`: `Cache-Control: no-cache` para `/sw.js` e `Content-Type: application/manifest+json` para o manifesto
- [ ] Confirmar que o rewrite do SPA não devolve `index.html` para `/sw.js`, `/manifest.webmanifest` nem `/icons/*`
- [ ] Confirmar no Preview (onde a CSP é imposta) que a política atual não bloqueia o *service worker* nem o manifesto; ajustar `worker-src` e `manifest-src` só se o console acusar violação
- [ ] Registrar nas specs que o *service worker* guarda apenas arquivos estáticos públicos

**Especificação:** `../../deploy/vercel-supabase.md`; `../../vercel.json`.
**Dependências:** PWA01, PWA02.
**Estimativa:** 30 minutos a 1 hora.

## PWA04 — Foto direto da câmera

- [ ] Em Nova análise (e no cadastro da armadilha com foto de identificação): dois botões, "Tirar foto" (`capture="environment"`) e "Escolher da galeria"; um só campo com `capture` impediria escolher fotos já salvas
- [ ] Reduzir a foto **no navegador** antes do envio (lado maior até 1600 px, JPEG com qualidade em torno de 0,85, respeitando a orientação EXIF), para caber nos 4 MB e nos 20 MP da API; o modelo redimensiona para 768 × 576 de qualquer forma
- [ ] Manter as validações atuais de tipo e a mensagem de erro por código
- [ ] Testes: foto grande é reduzida; foto pequena segue inalterada; falha ao ler a imagem mostra erro claro

**Especificação:** `../plan/api/api_spec.md` (restrições de upload, 2.4).
**Dependências:** nenhuma (pode andar em paralelo com PWA01 a PWA03).
**Estimativa:** 1 a 2 horas.

## PWA05 — Verificação e documentação

- [ ] DevTools → Application: manifesto sem erros, *service worker* ativo e o site reconhecido como instalável (Preview e produção)
- [ ] Android (Chrome): instalar, abrir em tela cheia e enviar uma foto pela câmera
- [ ] iOS (Safari): "Adicionar à Tela de Início" e abrir como aplicativo
- [ ] Offline: sem rede, o casco abre com o aviso; nenhuma chamada `/api` sai do cache; o Cache Storage não contém dado de usuário, nem depois do logout
- [ ] README, `docs/EXECUCAO.md` e `docs/ARQUITETURA.md` com a seção "Instalar no celular"; `CHANGELOG.md` atualizado

**Dependências:** PWA01 a PWA04.
**Estimativa:** 1 hora.

---

# 4. Decisões pendentes (do mantenedor)

| ID | Decisão | Recomendação |
| --- | --- | --- |
| D1 | Forma de implementar: manifesto e *service worker* escritos à mão, ou o plugin `vite-plugin-pwa` | **À mão**, sem dependência nova. O plugin é uma dependência nova e exige confirmação expressa. |
| D2 | O que o aplicativo faz offline | Só abrir o casco com o aviso. Sem fila de envio offline. |
| D3 | Câmera: dois botões (tirar foto e galeria) ou um só | **Dois botões.** |
| D4 | Reduzir a foto no navegador antes do envio | **Sim**, é necessário para fotos de câmera de celular. |

Até que D1 a D4 sejam confirmadas, esta task **não autoriza implementação**.

---

# 5. Riscos

- **Cache de dados autenticados:** o maior risco de uma PWA neste sistema. Mitigado pela regra de PWA02: só o casco público é guardado, e `/api` passa sempre pela rede.
- **Atualização presa:** um `sw.js` com cache longo prenderia usuários numa versão antiga. Mitigado por PWA03.
- **iOS:** o Safari tem suporte mais restrito a PWA (sem aviso de instalação automático). O uso é instalar manualmente pelo menu Compartilhar.
- **Redução da foto:** muda o arquivo enviado (EXIF é descartado, o que é bom para a privacidade). O modelo recebe a mesma imagem final de 768 × 576, mas vale conferir a cobertura medida em algumas fotos antes e depois da redução.

---

# FIM DA TASK
