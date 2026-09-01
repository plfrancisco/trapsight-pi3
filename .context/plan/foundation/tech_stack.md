# TECH STACK — Projeto Integrador

**Versão:** 1.0
**Status:** ATIVO
**Escopo:** decisões tecnológicas, estrutura de código e justificativas

---

# 1. Visão geral da arquitetura

```text
┌─────────────────────────────────────────────┐
│  Frontend (React + Vite + Tailwind + TS)    │
│  Upload de imagem → exibe resultado visual  │
└──────────────────┬──────────────────────────┘
                   │ REST API
┌──────────────────▼──────────────────────────┐
│  Backend (FastAPI + Python)                 │
│  Serve o modelo, processa imagem, retorna   │
│  máscara + percentual + status              │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  Modelo de ML (PyTorch + U-Net)             │
│  Segmentação da superfície adesiva          │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  PostgreSQL (futuro)                        │
│  Histórico de análises, armadilhas, clientes│
└─────────────────────────────────────────────┘
```

---

# 2. Backend

| Componente | Tecnologia | Justificativa |
|---|---|---|
| Linguagem | Python 3.11+ | Padrão de mercado para ML/CV |
| Framework web | FastAPI | Async, tipagem, docs automáticas em `/docs`, fácil de servir modelo via API REST. Mesma stack usável quando virar produto real |
| Servidor | Uvicorn | ASGI padrão para FastAPI |

---

# 3. Frontend

| Componente | Tecnologia | Justificativa |
|---|---|---|
| Framework | React + TypeScript | Base sólida, membros do grupo já conhecem, escalável para PWA no futuro |
| Build tool | Vite | Rápido, zero config, HMR |
| Estilização | Tailwind CSS | Produtividade, sem escrever CSS manual |
| Componentes UI | A definir, se necessário | Para o MVP, HTML + Tailwind bastam. Radix/shadcn pode entrar depois |

> **Decisão:** frontend simples no MVP — sem TanStack Router/Query/Start e sem
> biblioteca de componentes pesada. O frontend faz upload de uma imagem, chama
> a API do FastAPI e exibe o resultado. Se no futuro virar PWA ou produto,
> adiciona-se roteamento e gerência de estado mais robustos.

---

# 4. Modelo e machine learning

## 4.1 Componentes

| Componente | Tecnologia | Justificativa |
|---|---|---|
| Framework de ML | PyTorch | Flexibilidade, comunidade ativa, padrão acadêmico |
| Biblioteca de segmentação | `segmentation_models_pytorch` (smp) | Fornece U-Net com encoder pré-treinado em poucas linhas. Trocar de arquitetura (U-Net → FPN → DeepLabV3) vira um parâmetro, permitindo comparação no relatório com esforço mínimo |
| Arquitetura | U-Net com encoder ResNet34 | Referência para segmentação semântica; ResNet34 equilibra capacidade e tamanho |
| Transfer learning | Encoder pré-treinado em ImageNet | **Decisão crítica** — o encoder já reconhece bordas, texturas e formas, o que viabiliza o treino com o dataset pequeno do projeto. Sem isso há risco real de não convergência |
| Training loop | PyTorch puro, sem Lightning | Poucos experimentos previstos; escrever o loop dá controle e entendimento do processo, relevante para a defesa acadêmica. Lightning fica como opção futura |
| Geração sintética | OpenCV + Pillow + Albumentations | Gerar imagens de armadilhas com máscaras automáticas |
| Augmentation | Albumentations | Leve, integra com PyTorch, augmenta imagem e máscara juntos |
| Métricas | torchmetrics | IoU/Dice, erro percentual, matriz de confusão |
| Baseline comparativo | OpenCV (threshold de cor) | Ver seção 4.2 |

## 4.2 Baseline clássico com OpenCV

Antes do modelo treinado, implementar uma solução clássica: o refil adesivo
tem cor conhecida e uniforme, os insetos destoam dela — contar os pixels que
destoam dá um percentual de área coberta em poucas linhas de OpenCV.

**Não é um substituto do modelo.** Serve como referência de comparação:

- Sem baseline, o resultado é *"a U-Net atingiu X% de IoU"* — o avaliador não
  tem parâmetro para julgar se X é bom.
- Com baseline, o resultado é *"o método clássico atingiu X% e degradou sob
  variação de iluminação; a U-Net atingiu Y% e manteve Z%"* — isso demonstra
  com evidência que o deep learning era necessário, em vez de apenas afirmar.

Benefício adicional: se o baseline funcionar bem demais, isso é descoberto no
início do projeto, não na véspera da entrega.

## 4.3 Alternativas avaliadas e descartadas

| Alternativa | Motivo da rejeição |
|---|---|
| YOLOv8/v11-seg | Faz segmentação de **instâncias** (identifica cada inseto), contrariando a decisão de medir área em vez de contar. Além disso, a licença AGPL-3.0 é um problema concreto dada a empresa parceira real |
| PyTorch Lightning | Abstração útil para muitos experimentos; com o volume previsto, o boilerplate manual é aceitável e traz mais entendimento |
| TensorFlow/Keras | Sem vantagem técnica no caso; ecossistema de segmentação menos rico que o do PyTorch (`smp`) |
| U-Net escrita manualmente | Cerca de 150 linhas para o mesmo resultado que `smp` entrega em 3, e sem pesos pré-treinados por padrão |

---

# 5. Banco de dados

| Componente | Tecnologia | Justificativa |
|---|---|---|
| Banco | PostgreSQL | Dados fortemente relacionais; tipos adequados a série temporal e metadados flexíveis; é o banco que seria usado em produção |
| ORM | SQLAlchemy | Padrão da indústria, documentação vasta — decisivo sob prazo |
| Migrations | Alembic | Integração nativa com SQLAlchemy; usado desde a primeira tabela |

> **O banco entra no MVP.** A decisão anterior de tratá-lo como opcional foi
> revista: sem histórico o sistema é apenas um classificador de imagem; com
> histórico é um sistema de monitoramento capaz de projetar quando a armadilha
> saturará, que é o valor de negócio da proposta.

Entidades do MVP: `armadilha`, `refil` e `analise`. Modelo completo,
justificativas e regras de persistência em `../data/data_model.md`.

---

# 6. Infraestrutura

| Componente | Tecnologia | Justificativa |
|---|---|---|
| Containerização | Docker + Docker Compose | Ambiente reproduzível, fácil de subir backend, frontend e banco juntos |
| Deploy | **Fora do escopo do MVP** | A apresentação roda via Docker Compose local. Publicar em servidor é evolução posterior, não decisão pendente |

## 6.1 O que roda em container

| Componente | Execução |
|---|---|
| PostgreSQL | Docker |
| Backend (FastAPI) | Docker |
| Frontend (React) | Docker |
| **Treino do modelo** | **Nativo ou Colab — fora do Docker** |

O treino fica fora do Docker deliberadamente: GPU passthrough via WSL2 no
Windows funciona, mas o esforço de configuração não se justifica no escopo do
projeto. O treino é um processo offline que produz um arquivo de pesos, e esse
arquivo é montado como volume no container do backend.

---

# 7. Ambiente de desenvolvimento

| Componente | Tecnologia | Observação |
|---|---|---|
| Gerenciador Python | uv, com `pyproject.toml` | Gera lockfile, atendendo à exigência de reprodutibilidade das regras. Exporta `requirements.txt` para o build Docker |
| Gerenciador Node | npm | |
| Linter/formatter Python | Ruff | Substitui flake8, black e isort |
| Linter/formatter JS/TS | ESLint + Prettier | |
| GPU para treino | Local (NVIDIA) | Disponível no grupo; sem limite de sessão e iteração mais rápida que serviços em nuvem |
| Tracking de experimentos | Weights & Biases | Gratuito para uso acadêmico; os gráficos são aproveitados diretamente no relatório e todo o grupo acompanha os mesmos runs |

---

# 8. Estrutura de pastas do código

Proposta, a ser confirmada no início da implementação:

```text
backend/
├── src/
│   ├── api/            # rotas FastAPI (upload, análises, armadilhas)
│   ├── entities/       # entidades ORM (armadilha, refil, analise)
│   ├── repositories/   # acesso ao banco
│   ├── services/       # regras de negócio sem HTTP nem SQL (cálculos, orquestração)
│   ├── inference/      # pipeline de inferência (imagem → status)
│   ├── networks/       # definição da U-Net e do baseline OpenCV
│   └── config/         # configurações e constantes
├── migrations/         # migrations do banco
├── training/           # scripts de treino (executados fora do servidor)
│   ├── train.py
│   ├── evaluate.py
│   └── generate_synthetic.py
├── requirements.txt
└── Dockerfile

frontend/
├── src/
│   ├── components/     # componentes React reutilizáveis
│   ├── pages/          # dashboard, detalhe, nova análise, cadastro
│   └── services/       # chamadas à API
├── package.json
└── Dockerfile

data/                   # NÃO versionado
├── synthetic/          # dataset sintético gerado
├── real/               # fotos reais da empresa
├── masks/              # máscaras de segmentação
└── uploads/            # imagens analisadas, referenciadas por analise.caminho_imagem

models/                 # NÃO versionado
└── checkpoints/        # pesos treinados, montados como volume no backend

notebooks/              # exploração e prototipagem

docker-compose.yml
```

> **Nota sobre nomenclatura:** a rede neural fica em `src/networks/`, não em
> `src/models/`. Com banco de dados no projeto, `models` é ambíguo — em stacks
> web o termo designa entidades de persistência. Separar `entities/` (ORM) de
> `networks/` (arquitetura da rede) elimina a ambiguidade.

---

# 9. Pendências

Nenhuma pendência de decisão técnica.

Pendências que dependem de informação externa estão registradas em
`project_overview.md` e `hardware_armadilha.md`.

---

# FIM DO TECH STACK
