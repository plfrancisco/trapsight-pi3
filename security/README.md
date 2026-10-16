# Suíte de segurança e invasão do TrapSight

Testes de invasão e varreduras com ferramentas do mercado, executados em
contêiner. Especificação completa:
[`.context/validation/seguranca_testes.md`](../.context/validation/seguranca_testes.md).
Origem dos requisitos: [`.context/plan/foundation/login.md`](../.context/plan/foundation/login.md).

> **Regra:** nada vai ao ar sem esta suíte verde e o relatório arquivado.
> **Nada pode ficar aberto:** nem o banco, nem o backend, nem qualquer serviço
> interno. Só as portas 80 e 443 do proxy.

## ⚠️ Uso autorizado

Aponte **somente** para sistemas do próprio projeto, com autorização:
o ambiente local, a **homologação** e o definitivo. Nunca para terceiros.
O modo `ativo` e os testes destrutivos rodam **apenas na homologação**
(cópia descartável, dados fictícios). Contra o definitivo, só os modos `rede`
e `passivo`.

## Pré-requisitos

Docker (e Git Bash no Windows). Nada é instalado na máquina: cada ferramenta
roda em contêiner e as dependências Python da suíte (`requirements.txt`)
ficam isoladas aqui, fora do produto.

## Execução cega (padrão para quem implementa o sistema)

Quem implementa **só executa**; o resultado vai cifrado para o revisor. Use
`executar_cego.sh` no lugar de `run_scans.sh`; ele aceita os mesmos modos e
variáveis:

```bash
bash security/scans/executar_cego.sh codigo pentest
```

A saída mostra apenas que a execução ocorreu, o arquivo cifrado
(`security/reports/relatorio_*.cms`), o SHA-256 e as etapas que **não puderam
ser executadas por problema de ambiente** (corrija e repita). **Nunca** mostra
aprovado, reprovado, contagens nem achados.

Regras: não leia `security/reports/`, não procure nem use a chave privada, não
use logs dos contêineres alvo para descobrir resultados e não altere testes nem
scripts para melhorar o resultado. O revisor abre o relatório com
`abrir_relatorio.sh` (usa a chave privada guardada **fora** do repositório, em
`~/.trapsight-seguranca/`). Detalhes e limites em
[`seguranca_testes.md`](../.context/validation/seguranca_testes.md), seção 11.

## Como rodar (modo direto, para o revisor)

Todos os comandos a partir da **raiz do repositório**. O modo direto imprime os
resultados: é de uso do revisor e do dono do projeto.

```bash
# 1) Sem alvo: segredos, dependências, SAST, Dockerfiles e imagens
bash security/scans/run_scans.sh codigo

# 2) Local (baseline): suíte caixa-preta contra a stack do Compose
export DOCKER_NET=projeto-integrador_default
export TARGET_URL=http://backend:8000          # dentro da rede do Compose
bash security/scans/run_scans.sh pentest

# 3) Homologação (duas passadas, ver abaixo)
export TARGET_URL=https://homologacao.exemplo.com
export TARGET_HOST=homologacao.exemplo.com
export SEC_USER_EMAIL=... SEC_USER_PASSWORD=...        # conta de teste descartável
export SEC_LOCKOUT_EMAIL=... SEC_LOCKOUT_PASSWORD=...  # conta separada (fica bloqueada)
bash security/scans/run_scans.sh tudo
CONFIRMO_HOMOLOGACAO=sim bash security/scans/run_scans.sh ativo

# 4) Definitivo (SEM ataque): portas, TLS e varredura passiva
export TARGET_URL=https://app.exemplo.com TARGET_HOST=app.exemplo.com
bash security/scans/run_scans.sh rede
bash security/scans/run_scans.sh passivo
```

Nunca coloque credenciais em arquivo versionado nem no histórico do shell
compartilhado; use variáveis de ambiente da sessão.

### Três passadas na homologação

Alguns testes precisam de configurações incompatíveis entre si (limite de IP
alto x baixo, prazos de sessão longos x curtos), então a suíte roda em três
passadas. `PASSADA` nomeia o relatório e `PYTEST_ARGS` escolhe os testes:

| Passada | Configuração da homologação | Comando |
|---|---|---|
| **1. Funcional** | Limite de tentativas por IP **elevado** (ex.: 100000); prazos de sessão padrão | `PASSADA=1 bash security/scans/run_scans.sh pentest` |
| **2. Limites** | Limite por IP e de análises com os **valores padrão** (30 falhas/15 min; 30 análises/min) | `PASSADA=2 SEC_RUN_RATE_LIMIT=1 PYTEST_ARGS='-k "test_limite_de_analises or test_limite_de_tentativas_por_ip"' bash security/scans/run_scans.sh pentest` |
| **3. Expiração** | `SEC_IDLE_TIMEOUT_SECONDS=5` e `SEC_ABSOLUTE_TIMEOUT_SECONDS=15` **também configurados no backend** | `PASSADA=3 PYTEST_ARGS='-k expiracao' bash security/scans/run_scans.sh pentest` |

Por que separar: o teste de limite por IP esgota o IP do executor (não se
consegue mais logar por 15 minutos, então **reinicie o backend ou espere**
antes de uma nova execução), e prazos curtos derrubariam a sessão dos outros
testes no meio da execução. O teste de limite por IP roda por último.

## Variáveis de ambiente

| Variável | Função |
|---|---|
| `TARGET_URL` | Origem do sistema (obrigatória) |
| `API_PREFIX` | Prefixo da API (padrão `/api`) |
| `TARGET_HOST` | Host para varredura de portas |
| `EXPECTED_OPEN_PORTS` | Portas permitidas (padrão `80,443`) |
| `DOCKER_NET` | Rede do Compose, para alvo local |
| `SEC_USER_EMAIL`, `SEC_USER_PASSWORD` | Conta de teste |
| `SEC_LOCKOUT_EMAIL`, `SEC_LOCKOUT_PASSWORD`, `SEC_LOCKOUT_THRESHOLD` | Conta do teste de bloqueio e limite (padrão 5) |
| `SEC_CHANGEPWD_EMAIL`, `SEC_CHANGEPWD_PASSWORD`, `SEC_CHANGEPWD_NEW` | Conta dos testes de troca e de política de senha |
| `SEC_DB_DSN_APP`, `SEC_DB_DSN_ADMIN` | DSN do usuário da aplicação (e, opcional, administrativo) para os testes de banco; o executor precisa estar na rede interna (`DOCKER_NET`) |
| `SEC_MAX_SESSIONS` | Limite de sessões simultâneas (padrão 5) |
| `SEC_IDLE_TIMEOUT_SECONDS`, `SEC_ABSOLUTE_TIMEOUT_SECONDS` | Prazos curtos da homologação |
| `SEC_RUN_RATE_LIMIT` | `1` liga os testes que esgotam limites |
| `CONFIRMO_HOMOLOGACAO` | `sim` libera o modo `ativo` |

## Como interpretar

* Cada execução gera `security/reports/AAAA-MM-DD_<commit>_<modo>/` (ignorado
  pelo Git) com `RESUMO.txt`, a saída bruta de cada ferramenta e `imagens.txt`
  com os **digests** das imagens usadas.
* Veredito do script: **APROVADO**, **REPROVADO** (código de saída 1) ou
  **INCOMPLETO** (código 3: há etapas não executadas, que **não contam como aprovadas**).
* Um teste `SKIPPED` (credencial ausente, limite desligado) é **não verificado**,
  nunca aprovado. Leia o motivo impresso por `-rs`.
* **Crítica ou alta bloqueia a publicação.** Média exige triagem por escrito.

## Estado esperado hoje

Os testes afirmam o estado **final** desejado. Antes de o login existir, os que
não exigem sessão (exposição, transporte, vazamento, autorização) **executam e
falham** (rotas abertas, sem HTTPS, `/docs` público): essa é a lista de
pendências. Os que exigem login ficam `SKIPPED`. Cada item implementado de
`login.md`, seção 15, deve levar os testes correspondentes ao verde.

## Estrutura

```text
security/
  README.md              este arquivo
  requirements.txt       pytest, httpx, pillow, psycopg (isolados do produto)
  pytest.ini
  cifra/certificado.pem  certificado PÚBLICO que cifra os relatórios (a chave privada fica fora do repo)
  pentest/               suíte caixa-preta, um arquivo por área (WSTG), mais a lista mínima de senhas
  scans/run_scans.sh     orquestrador das ferramentas em contêiner (modo direto, para o revisor)
  scans/executar_cego.sh executor cego: roda e cifra o relatório (para quem implementa)
  scans/abrir_relatorio.sh abre o relatório cifrado (somente o revisor)
  reports/               relatórios (ignorado pelo Git)
```

## Manutenção

Rota nova na API: acrescentar em `ROTAS_PROTEGIDAS`
(`pentest/test_07_autorizacao.py`) e, se ela receber texto, arquivo ou
parâmetro, nos testes de `test_08` e `test_09`. Nova porta, serviço ou rota
pública: atualizar a suíte **na mesma entrega**.
