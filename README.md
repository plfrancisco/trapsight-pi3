# TrapSight

**Visão computacional para medir a saturação de armadilhas adesivas e prever a hora de trocar o refil.**

O TrapSight analisa a foto de uma armadilha adesiva de mosquito, calcula **quanto da superfície já está coberta por insetos** e **estima em quantos dias ela vai saturar**, trocando a inspeção manual por um critério objetivo.

![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white) ![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?logo=pytorch&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white) ![React](https://img.shields.io/badge/React-61DAFB?logo=react&logoColor=black) ![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white) ![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)

> Projeto Integrador de Sistemas Inteligentes III — Fatec "Shunji Nishimura", Pompeia. **Em desenvolvimento.**

## O problema

Empresas de controle de pragas mantêm armadilhas adesivas em mercados e açougues e decidem a troca do refil por **inspeção visual**, sem critério objetivo. O resultado é um custo duplo:

- **Troca antecipada:** deslocamento da equipe e refil descartado com vida útil sobrando;
- **Troca tardia:** armadilha saturada, sem eficácia no controle de pragas.

O problema foi levantado com uma empresa real do setor, parceira do projeto.

## A solução

```mermaid
flowchart LR
    A[Foto da armadilha] --> B[Pré-processamento]
    B --> C[Segmentação<br/>U-Net]
    C --> D[Máscara de 3 classes<br/>fundo · placa limpa · placa coberta]
    D --> E[% de área coberta]
    E --> F{Status}
    F -->|abaixo de 40%| G[ok]
    F -->|40% a 70%| H[atenção]
    F -->|acima de 70%| I[trocar]
```

Além da leitura pontual, o sistema guarda o histórico de cada armadilha e **projeta quantos dias faltam para a saturação**, permitindo planejar a visita em vez de reagir a ela.

## Funcionalidades

- **Análise por imagem:** upload da foto, máscara de segmentação sobreposta, percentual de cobertura e status;
- **Dashboard operacional:** armadilhas ordenadas por urgência, miniatura da última foto analisada e painel de alertas, com navegação adaptada para celular;
- **Histórico e projeção:** evolução da cobertura por refil e previsão de dias até a saturação por regressão linear;
- **Timelapse:** reprodução das imagens de um refil sincronizada com o gráfico de evolução;
- **Ciclo de vida do refil:** registro de trocas, com histórico de duração de cada ciclo;
- **Modelos de armadilha pré-cadastrados:** o cadastro oferece o catálogo do fabricante (o primeiro é o StickFly K-45, com as dimensões do refil), em vez de texto livre;
- **Acesso por login:** contas criadas pelo administrador, com sessão segura (cookie `HttpOnly`) e senhas protegidas com Argon2id.

## Arquitetura

```mermaid
flowchart LR
    U[Navegador] --> F[Frontend<br/>React + TypeScript]
    F -->|REST + JSON| A[API<br/>FastAPI]
    A --> I[Inferência<br/>U-Net]
    A --> D[(PostgreSQL)]
    A --> S[(Imagens<br/>em disco)]
```

Os três serviços (frontend, API e banco) sobem juntos com Docker Compose. O treino do modelo roda fora do container e gera o arquivo de pesos que a API carrega na inicialização.

## Decisões técnicas

| Decisão                                                        | Por quê                                                                                                                          |
| --------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| **Medir área coberta em vez de contar insetos**            | Insetos colados se sobrepõem; área é um indicador mais robusto de saturação                                                  |
| **Segmentação em 3 classes** (fundo, placa limpa, placa coberta) | O percentual é calculado sobre a placa detectada, não sobre a imagem inteira; o resultado não depende do enquadramento da foto |
| **Dataset sintético primeiro, dados reais depois**           | Não existe base pública deste cenário; as máscaras nascem junto com a imagem, sem rotulagem manual                            |
| **Sprites de insetos brasileiros de fotos com licença aberta** | O banco usa observações do iNaturalist no Brasil (moscas, mosquitos, formigas, baratas, mariposas e besouros), com autor e licença de cada foto registrados |
| **Avaliação separada em sintético e real**                  | A distância entre as duas métricas mede o *domain gap* e diagnostica se o problema está no gerador ou no modelo              |
| **Baseline clássico (OpenCV) como comparação**              | Mostra com evidência, e não por afirmação, onde o modelo treinado supera um limiar de brilho                                  |
| **Transfer learning** (U-Net com encoder ResNet34 pré-treinado) | Viabiliza o treino com um dataset pequeno                                                                                         |
| **Projeção por regressão sobre todas as medições**          | Usar só a primeira e a última leitura amplifica o ruído de medição                                                           |
| **Regras no banco, não só na aplicação**                      | Restrições, chaves e um índice único parcial garantem no máximo um refil ativo por armadilha, mesmo com acessos concorrentes |
| **Erros padronizados com códigos estáveis**                  | O frontend decide o comportamento pelo código do erro, nunca pelo texto da mensagem                                            |

## Stack

| Camada         | Tecnologia                                                              |
| -------------- | ----------------------------------------------------------------------- |
| Modelo         | Python, PyTorch, `segmentation_models_pytorch`, OpenCV, Albumentations |
| Backend        | FastAPI, SQLAlchemy, Alembic, Pydantic                                  |
| Banco de dados | PostgreSQL                                                              |
| Frontend       | React, TypeScript, Vite, Tailwind CSS, Recharts                         |
| Infraestrutura | Docker, Docker Compose, Caddy (proxy reverso com HTTPS automático), Vercel (frontend), Supabase (banco) |
| Qualidade      | Ruff, pytest, ESLint                                                    |

## Status

| Etapa                                                              | Situação      |
| ------------------------------------------------------------------ | ------------- |
| Especificação técnica (arquitetura, modelo, API, telas, avaliação) | Concluída     |
| Ambiente de desenvolvimento e Docker Compose                       | Concluída     |
| Banco de dados (esquema, migrations, regras de integridade)        | Concluída     |
| API (endpoints, upload de imagem, histórico e projeção de saturação) | Concluída     |
| Interface web (dashboard, cadastro, nova análise e detalhe da armadilha prontos; timelapse em desenvolvimento) | Em andamento  |
| Login e hospedagem pública (frontend na Vercel e banco no Supabase; rodadas de teste de segurança pendentes) | Em andamento  |
| Gerador de dataset sintético e banco de sprites                    | Concluída     |
| Treinamento e avaliação do modelo (especificação do treino pronta; baseline e treino em desenvolvimento) | Em andamento  |
| Validação com fotos reais da empresa parceira                      | Não iniciada  |

Ainda não há resultados de modelo para reportar. Eles serão publicados aqui após a avaliação.

## Como executar

Pré-requisito: Docker Desktop.

```bash
# variáveis de ambiente (preencha os placeholders)
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# sobe banco, API e frontend
docker compose up --build
```

| Serviço   | Endereço                       |
| --------- | ------------------------------ |
| Frontend  | http://localhost:5173          |
| API (docs)| http://localhost:8000/docs     |

**Publicação online:** o protótipo está hospedado com o frontend na Vercel e o banco no Supabase, e o acesso exige login. O repositório também traz um Compose de produção (`docker-compose.prod.yml`) em que só o proxy (portas 80 e 443) fica público, usado nos testes de segurança locais. O desenho está em [`.context/plan/foundation/login.md`](.context/plan/foundation/login.md) e a suíte de testes de segurança em [`security/`](security/README.md).

Para desenvolver o backend fora do Docker, instale o [`uv`](https://docs.astral.sh/uv/) e use `uv sync`, `uv run ruff check .` e `uv run pytest` na pasta `backend/`. Os testes de integração precisam de um PostgreSQL com as migrations aplicadas (`uv run alembic upgrade head`). Com o banco do Compose ativo (`docker compose up -d db`), `scripts/testar-backend.sh` roda os testes em um banco separado dentro dele, sem subir outro PostgreSQL.

## Documentação

A especificação completa do sistema está em [`.context/`](.context/): visão geral, modelo de dados, contrato da API, telas, pipeline do modelo e critérios de avaliação. O ponto de partida é [`.context/plan/README.md`](.context/plan/README.md).

## Autor

**Pedro Lucas Francisco** — Tecnologia em Sistemas Inteligentes, Fatec Pompeia.
