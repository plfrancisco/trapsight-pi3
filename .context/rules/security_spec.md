# SECURITY SPEC — Projeto Integrador

**Versão:** 1.1
**Status:** ATIVO
**Escopo:** requisitos de segurança obrigatórios para o backend, frontend e
infraestrutura do projeto

---

# 1. Objetivo

Definir controles de segurança específicos para esta stack (FastAPI, React,
PostgreSQL, upload de imagem, modelo PyTorch, Docker) — não uma lista
genérica de boas práticas. Cada item aqui responde a um vetor de ataque real
para o que este sistema faz.

Este documento tem a mesma autoridade normativa que os demais em
`.context/rules/`. Uma alteração que toque entrada de usuário, upload,
autenticação, banco de dados ou dependências deve ser confrontada contra
este documento antes de ser aprovada.

---

# 2. Modelo de ameaça e escopo

## 2.1 Escopo do MVP

O MVP roda **localmente ou em rede fechada, para demonstração** — não é
implantado publicamente na internet. Isso **não reduz nenhum controle deste
documento**, incluindo a regra da seção 3. Reduz apenas a urgência de alguns
itens marcados explicitamente como "Fase 2" na seção 10 — ex.: HTTPS
obrigatório só importa quando houver rede externa envolvida. Segredo
hardcoded é problema em qualquer ambiente, local ou não: entra no histórico
do Git, é lido por qualquer pessoa com acesso ao repositório, e sobrevive à
mudança de ambiente sem que ninguém perceba.

## 2.2 Superfícies de ataque relevantes

| Superfície | Por quê |
|---|---|
| Upload de imagem (`POST /api/analises`) | Único endpoint que recebe arquivo binário de origem externa |
| Campos de texto livre (`identificador`, `localizacao`, `modelo`) | Entram no banco e são exibidos no frontend |
| Carregamento do modelo (`MODEL_WEIGHTS_PATH`) | Arquivo binário desserializado na inicialização do backend |
| CORS | Define quem pode chamar a API a partir de um navegador |
| Variáveis de ambiente e segredos | Credenciais de banco, chaves de API, caminhos de sistema — ver seção 3 |

## 2.3 Fora de escopo nesta versão

Autenticação de usuário e autorização por papel — o MVP não tem contas de
usuário (`project_overview.md`, seção 5.2). A ausência de autenticação é um
**risco aceito e documentado**, não um esquecimento — ver seção 4.

---

# 3. Regra absoluta: nenhum segredo em código

Esta é a regra de maior prioridade neste documento e vale **incondicionalmente
— rodando localmente, em demonstração, ou em produção.** Não é relaxada pelo
projeto ser um MVP acadêmico nem por não haver plano de expor o sistema à
internet.

## 3.1 O que conta como segredo

- Senha e string de conexão de banco de dados (`DATABASE_URL`)
- Qualquer chave de API — inclusive de serviços usados só em desenvolvimento
  (ex.: chave do Weights & Biases para tracking de experimentos,
  `tech_stack.md`, seção 7)
- Chave ou token de autenticação, quando a Fase 2 os introduzir (seção 4)
- Qualquer credencial de terceiro (e-mail, serviço de nuvem, webhook)

## 3.2 Controles obrigatórios

| Controle | Detalhe |
|---|---|
| Nenhum segredo é escrito diretamente em código-fonte, em nenhuma linguagem do projeto | Nem "temporariamente para testar" — um valor hardcoded esquecido é a causa mais comum de vazamento de credencial |
| Todo segredo é lido exclusivamente de variável de ambiente | Nunca de arquivo de configuração versionado, nunca de constante no código |
| `.env` contém os valores reais e está no `.gitignore`; `.env.example` contém apenas placeholders e é o único versionado | Conforme `../task/completed/current_task_ambiente.md`, AMB03 — os exemplos ali já seguem esta regra |
| Nenhum segredo aparece em log, mensagem de erro, resposta de API, commit message ou comentário de código | Ver também seção 9 (tratamento de erro) |
| Nenhum segredo é copiado para dentro de uma imagem Docker em tempo de build | Entra apenas via variável de ambiente em tempo de execução — ver seção 10.1 |
| Se um segredo for commitado por engano, ele é considerado comprometido | Trocar o segredo é obrigatório; remover do arquivo atual não é suficiente — ele permanece no histórico do Git |

## 3.3 Verificação

Antes de qualquer commit que toque configuração, variáveis de ambiente ou
integração com serviço externo, revisar manualmente o diff em busca de
valores que pareçam credencial (strings longas, prefixos conhecidos de chave
de API, `://usuario:senha@` em URLs). Não depender apenas de lembrar a
regra — o hábito de checar o diff antes de commitar é o controle real.

---

# 4. Autenticação — risco aceito

O MVP não implementa autenticação. Todos os endpoints de escrita
(`POST`/`PATCH`/`DELETE`) estão abertos a qualquer cliente que alcance a
API.

**Controle obrigatório de compensação:** o backend **nunca** deve ser
exposto a uma rede não confiável (internet pública) sem autenticação
adicionada antes. `CORS_ORIGENS` restrito a origens conhecidas (seção 7) é
mitigação parcial para navegador, não para chamada direta à API.

Adicionar autenticação é pré-requisito obrigatório antes de qualquer
implantação além de demonstração controlada — registrado como pendência de
Fase 2 na seção 10, não implementado agora por decisão de escopo, não por
descuido. Quando implementada, qualquer chave/segredo de autenticação segue
integralmente a seção 3.

---

# 5. Validação de upload de imagem

Aplica-se a `POST /api/analises` (`../plan/api/api_spec.md`, seção 6.1).

## 5.1 Validação de conteúdo, não apenas de extensão

| Controle | Detalhe |
|---|---|
| Verificar o tipo real do arquivo pelos primeiros bytes (magic bytes), não pela extensão do nome nem pelo `Content-Type` declarado pelo cliente | Um arquivo `.jpg` pode conter qualquer coisa — o cliente controla ambos os campos |
| Rejeitar qualquer tipo fora de JPEG/PNG após essa verificação | Conforme `api_spec.md`, seção 2.4 |
| Limite de tamanho de 10 MB aplicado **antes** de carregar o arquivo inteiro em memória | Streaming ou verificação de `Content-Length`, não `try/except` após o carregamento completo |

## 5.2 Proteção contra decompression bomb

Uma imagem pequena em disco pode se expandir para gigabytes em memória ao
ser decodificada (ex.: PNG com dimensões absurdas). Isso é uma negação de
serviço, não uma falha de tamanho de arquivo.

| Controle | Detalhe |
|---|---|
| Definir limite explícito de dimensões decodificadas (ex.: `PIL.Image.MAX_IMAGE_PIXELS`) antes de processar qualquer upload | Nunca desabilitar esse limite globalmente por conveniência |
| Rejeitar imagem cuja resolução decodificada exceda um teto razoável (ordem de dezenas de milhões de pixels) | Nenhuma foto de armadilha legítima chega perto disso |

## 5.3 Nome e caminho do arquivo

| Controle | Detalhe |
|---|---|
| Nunca usar o nome de arquivo enviado pelo cliente para compor o caminho de gravação | Abre caminho para path traversal (`../../etc/passwd`) |
| Gerar o nome do arquivo no servidor (ex.: UUID da análise) | O nome original do cliente, se guardado, fica apenas como metadado, nunca como caminho |
| Gravar exclusivamente dentro de `UPLOADS_DIR` (seção 7), validando que o caminho resultante não escapa do diretório | Checagem explícita, não apenas confiança na geração do nome |

---

# 6. Banco de dados

## 6.1 Injeção de SQL

| Controle | Detalhe |
|---|---|
| Toda consulta passa pelo ORM (SQLAlchemy) ou por parâmetros vinculados | Nunca concatenar ou formatar string para montar SQL a partir de entrada de usuário |
| Proibido SQL cru construído a partir de campo de texto livre (`identificador`, `localizacao`) | Mesmo para filtros ou ordenação dinâmica — usar a API de expressões do ORM |

Esta regra já está implícita no uso do SQLAlchemy definido em
`../plan/foundation/tech_stack.md`, mas é reforçada aqui como controle de
segurança explícito, não apenas escolha de produtividade.

## 6.2 Credenciais

| Controle | Detalhe |
|---|---|
| `DATABASE_URL` só via variável de ambiente, conforme a regra absoluta da seção 3 | Nunca hardcoded, nunca em exemplo com credencial real |
| Usuário do banco usado pela aplicação não é o superusuário do Postgres | Princípio de menor privilégio, mesmo em ambiente de desenvolvimento |

---

# 7. CORS e configuração

| Controle | Detalhe |
|---|---|
| `CORS_ORIGENS` é lista explícita de origens, nunca `*` | Conforme `../plan/api/api_spec.md`, seção 2.6 |
| Variáveis sensíveis nunca aparecem em log, mensagem de erro ou resposta da API | Ver seção 9 |

---

# 8. Carregamento do modelo

Esta é uma superfície de ataque específica de aplicações que carregam
modelos PyTorch, frequentemente ignorada.

## 8.1 Desserialização segura

`torch.load` usa `pickle` por padrão, que pode executar código arbitrário se
o arquivo carregado for malicioso — desserializar um checkpoint não é uma
operação neutra.

| Controle | Detalhe |
|---|---|
| Carregar pesos com `weights_only=True` (ou equivalente da versão do PyTorch em uso) | Restringe a desserialização a tensores, impedindo execução de código arbitrário embutido no arquivo |
| `MODEL_WEIGHTS_PATH` aponta **sempre** para um caminho local controlado pelo time, nunca para um upload de usuário ou URL externa não verificada | O modelo é um artefato de build/deploy, não um dado de entrada da aplicação |

## 8.2 Falha de inicialização

Já especificado em `../plan/model/modelo_spec.md`, seção 8: pesos ausentes
ou inválidos impedem a aplicação de subir. Reforço de segurança: essa falha
**não deve** expor caminho interno de arquivo nem stack trace ao cliente —
apenas ao log do servidor.

---

# 9. Tratamento de erro e logs

| Controle | Detalhe |
|---|---|
| O corpo de erro retornado ao cliente (`api_spec.md`, seção 2.2) nunca inclui stack trace, caminho de arquivo do servidor, ou detalhe de configuração interna | `detalhes` no corpo de erro é para contexto do domínio (ex.: `armadilha_id`), não para depuração interna |
| Logs do servidor podem conter detalhe técnico completo | Log não é resposta pública |
| Nunca logar segredos — `DATABASE_URL`, chaves de API ou qualquer item da seção 3.1 | Nem em nível de debug; log persiste em disco e é frequentemente compartilhado sem o mesmo cuidado que o código |

---

# 10. Infraestrutura e dependências

## 10.1 Docker

| Controle | Detalhe |
|---|---|
| Containers rodam com usuário não-root | Evita escalonamento de privilégio caso haja vulnerabilidade na aplicação |
| Imagens base mínimas (`-slim`/`-alpine` quando compatível) | Reduz superfície de vulnerabilidades herdadas da imagem |
| Nenhum segredo copiado para dentro da imagem em tempo de build | Reforço direto da seção 3.2 — segredos entram só via variável de ambiente em tempo de execução |

## 10.2 Dependências

| Controle | Detalhe |
|---|---|
| Lockfile commitado (`uv.lock`, `package-lock.json`) | Build reprodutível, conforme `tech_stack.md`, seção 7 |
| Atualização de dependência é uma mudança revisada, não automática | Alinhado com a seção 4.2 de `ai_development_rules.md` — mudar dependência exige nova confirmação |

## 10.3 Pendente para além do MVP (Fase 2)

- [ ] Autenticação e autorização (seção 4)
- [ ] Rate limiting no endpoint de análise, se exposto além de demonstração
      controlada — inferência é operação computacionalmente cara e pode ser
      usada para negação de serviço
- [ ] HTTPS obrigatório em qualquer implantação além de localhost
- [ ] Rotina de verificação de vulnerabilidades conhecidas nas dependências
      (ex.: `pip-audit`, `npm audit`) antes de cada entrega relevante
- [ ] Gerenciador de segredos dedicado (ex.: Doppler, Vault) se o número de
      integrações externas crescer além do que variáveis de ambiente simples
      conseguem organizar com segurança

---

# 11. Frontend

| Controle | Detalhe |
|---|---|
| Nunca usar `dangerouslySetInnerHTML` com dado vindo da API sem sanitização | Campos de texto livre (`identificador`, `localizacao`) são exibidos na interface e podem conter qualquer conteúdo |
| React escapa texto por padrão em renderização normal (`{variavel}`) | Suficiente na maioria dos casos — o risco é justamente contornar esse comportamento padrão sem necessidade |
| Nenhuma chave de API ou segredo em código do frontend, incluindo variáveis `VITE_*` | Tudo que vai para `import.meta.env` no Vite é embutido no bundle e visível a qualquer pessoa que abrir o navegador — `VITE_API_URL` é público por natureza (é só um endereço), mas nenhuma credencial deve seguir esse caminho |

---

# 12. Pendências

- [ ] Confirmar a biblioteca de detecção de tipo real de arquivo a usar
      (ex.: `python-magic`) e integrá-la em `../task/completed/current_task_api.md`, API07
- [ ] Definir usuário não-root nas imagens Docker de `../task/completed/current_task_infra.md`,
      INFRA03
- [ ] Revisar este documento antes de qualquer implantação além de
      demonstração local/controlada

---

# FIM DO SECURITY SPEC
