# Changelog

Todas as mudanças relevantes do TrapSight ficam registradas aqui. O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e as versões seguem o [Versionamento Semântico](https://semver.org/lang/pt-BR/). Enquanto a versão principal for `0`, a API e o comportamento podem mudar entre versões menores.

Cada versão tem uma tag Git (`vX.Y.Z`). Para ver o código de uma versão: `git checkout v0.1.0`.

## [Não lançado]

### Adicionado

- **Exclusão de operadores** na tela Contas, com confirmação (`DELETE /api/usuarios/{id}`): só o gerente pode excluir, a conta gerente não pode ser excluída, as sessões do operador são removidas junto com a conta e o evento `conta_excluida` é registrado.

- **Licença MIT** (`LICENSE`), política de segurança (`SECURITY.md`, com relato privado de vulnerabilidades) e guia de contribuição (`CONTRIBUTING.md`).
- **`docs/ARQUITETURA.md`**, com a arquitetura, as decisões técnicas, as tecnologias, a estrutura do repositório e a situação das etapas.

### Alterado

- **README reescrito** como porta de entrada (cerca de metade do tamanho): problema e solução, resultados e limites do modelo, demonstração com login de teste e pasta de fotos, execução local, testes e links para a documentação.

### Removido

- **CI do GitHub Actions** (`.github/workflows/ci.yml`): o projeto tem um só mantenedor e os testes passam a rodar localmente. O arquivo continua no histórico do Git.

## [0.1.0] - 2026-11-03

Primeiro protótipo funcional: análise de fotos com o modelo treinado, histórico por refil, previsão de saturação, login por papéis e publicação na Vercel com banco no Supabase.

### Adicionado

- **Análise por imagem:** envio de foto (JPEG ou PNG, até 4 MB), percentual coberto da placa, status (ok, atenção ou trocar) e versão do modelo.
- **Modelo de segmentação:** U-Net com encoder ResNet34 pré-treinado, em 3 classes (fundo, placa limpa e placa coberta), treinada em imagens sintéticas e exportada para ONNX (`backend/models/modelo.onnx`, versão `v0.1.0-e1+a982b9a5`). No conjunto de teste sintético de 450 imagens: Dice da classe "placa coberta" de 0,966, erro médio de 0,24 ponto percentual e 99,3% de acerto no status.
- **Inferência em ONNX Runtime**, em CPU e sem PyTorch em produção, com conferência do SHA-256, das dimensões e da saída do modelo na inicialização.
- **Painel** com as armadilhas ordenadas por urgência, miniatura da última foto e painel de alertas.
- **Histórico por refil, gráfico de evolução e previsão de dias até a saturação** por regressão linear.
- **Troca de refil** com a duração de cada ciclo registrada, catálogo de modelos de armadilha (StickFly K-45) e foto de identificação da armadilha.
- **Imagem com a máscara do modelo** (área coberta em magenta) nas telas de análise, com botão para ver a foto original.
- **Barra de progresso** durante a análise, que vai a 100% quando o resultado chega.
- **Índice de saturação do refil** nas telas: o limiar de troca (20% de cobertura) aparece como 80%.
- **Login e papéis:** contas criadas por um gerente (um só), troca da senha inicial, sessão em cookie `HttpOnly`, proteção contra CSRF, bloqueio por tentativas, limites de uso e senhas com Argon2id. Administração por linha de comando.
- **Publicação:** Vercel (frontend e API) e Supabase (PostgreSQL com RLS e papéis de permissão mínima).
- **Qualidade e segurança:** CI no GitHub Actions, suíte de testes de segurança e documentação (README, guia de execução em `docs/EXECUCAO.md` e especificações em `.context/`).

### Alterado

- **Política de senha:** de 8 a 128 caracteres, com ao menos uma letra e um número (antes eram 15 caracteres sem regra de composição).

### Limitações conhecidas

- O modelo foi medido apenas em imagens sintéticas.
- A análise leva cerca de 5 segundos por foto em CPU, mais na primeira chamada depois de um período parado.
- Os limites de análises por minuto e de contas por hora valem por instância do servidor, não de forma global.
- O relatório final dos testes de invasão está em andamento.
- A CSP está imposta apenas no Preview da `dev`; na produção ela segue em modo de relatório.

[0.1.0]: https://github.com/plfrancisco/trapsight-pi3/releases/tag/v0.1.0
