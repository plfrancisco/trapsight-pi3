# Gerador de dataset sintético

O gerador cria cenas de refis adesivos, máscaras semânticas e metadados a
partir de um catálogo local de sprites PNG com transparência e licença
registrada. Os artefatos gerados devem ficar fora do código-fonte versionado.

## Importar bibliotecas reais

O conversor reúne os sprites UMS e os sprites filtrados da Amazônia em uma
nova pasta de catálogo fora do repositório. A escala UMS é calculada com a
resolução efetiva do scan (`47,24 × escala` pixels/mm); a escala Amazônia é
estimada pela distribuição UMS da ordem equivalente. As categorias pequeno,
médio e grande são definidas pelos tercis dos tamanhos físicos UMS. Cada
registro preserva a classe original, autoria, fonte, licença e se a escala foi
medida ou estimada. O conversor falha se faltar procedência, licença ou PNG.

```powershell
cd backend
uv run python -m training.importar_sprites_reais `
  --ums-sprites "D:\dados\trapsight\sprites-ums" `
  --ums-meta "D:\dados\trapsight\dataset-real-ums\meta.json" `
  --amazonia-sprites "D:\dados\trapsight\sprites-amazonia" `
  --amazonia-fonte "https://doi.org/10.6084/m9.figshare.28688198" `
  --amazonia-licenca "CC BY 4.0" `
  --amazonia-autor "Lucas F. Colares; Carlos A. Peres; Cristian S. Dambros" `
  --saida "D:\dados\trapsight\sprites-reais" `
  --semente 20261021
```

Atribuições declaradas: Ong & Lim (2025), *An annotated image dataset of urban
insects for computer vision and deep learning*, Figshare,
[DOI 10.6084/m9.figshare.28280792.v1](https://doi.org/10.6084/m9.figshare.28280792.v1),
CC BY 4.0; Colares, Peres & Dambros (2025), *5-fold dataset for deep learning
training using insect images from sticky traps in Central Amazon*, Figshare,
[DOI 10.6084/m9.figshare.28688198](https://doi.org/10.6084/m9.figshare.28688198),
CC BY 4.0. Os PNGs importados são cópias de trabalho fora do repositório; os
arquivos originais permanecem intactos.

## Catálogo de sprites

Prepare um diretório com `manifest.json` e os arquivos PNG listados nele. Cada
registro declara caminho relativo, categoria, grupo, autor, fonte e licença.
O catálogo deve conter as categorias `pequeno`, `medio` e `grande`.

```json
{
  "sprites": [
    {
      "arquivo": "insetos/pequeno-01.png",
      "categoria": "pequeno",
      "grupo": "mosquito",
      "autor": "Nome do autor",
      "fonte": "https://exemplo.org/conjunto",
      "licenca": "CC-BY-4.0",
      "especie": "espécie identificada",
      "fragmentado": false
    },
    {
      "arquivo": "insetos/medio-01.png",
      "categoria": "medio",
      "grupo": "mosca",
      "autor": "Nome do autor",
      "fonte": "https://exemplo.org/conjunto",
      "licenca": "CC-BY-4.0",
      "fragmentado": true
    },
    {
      "arquivo": "insetos/grande-01.png",
      "categoria": "grande",
      "grupo": "besouro",
      "autor": "Nome do autor",
      "fonte": "https://exemplo.org/conjunto",
      "licenca": "CC-BY-4.0"
    }
  ]
}
```

Os nomes e a licença do exemplo são ilustrativos. Use apenas sprites cuja
origem e autorização de uso tenham sido verificadas. O gerador valida o
manifesto e o canal alfa; ele não cria nem remove o fundo dos sprites.


## Coleta do iNaturalist

O coletor consulta a API pública sem chave, usa place_id 6878 (Brasil),
observações research, licenças cc0, cc-by e cc-by-nc, e URLs de foto medium
ou maiores. A meta padrão é 60 fotos únicas por grupo: mosca, mosquito,
formiga, barata, mariposa e besouro. O manifesto registra id da observação,
URL, autor, licença, táxon e grupo.

Defina um diretório absoluto fora do repositório. Fotos, manifesto e caches da
API e do modelo rembg ficam abaixo dele:

```powershell
$env:TRAPSIGHT_TRAINING_DATA_DIR = "D:\dados\trapsight\treino"
uv sync --group treino
uv run python -m training.coletar_inaturalist --fotos-por-grupo 60 --semente 20261021
```

O coletor limita as requisições a uma por segundo. Respostas da API e fotos
existentes são reutilizadas em execuções seguintes; se interrompido, execute
o mesmo comando para continuar. Nenhuma chave ou token é lido ou gravado.

## Preparar sprites

O modo iNaturalist usa o modelo isnet-general-use do rembg para gerar uma
máscara, mantém o maior componente conectado e salva cada recorte como PNG
RGBA. Modelos e fotos permanecem no diretório externo. O modo COCO continua
aceitando polígonos; informe fonte, licença e, se necessário, grupo-coco.

```powershell
uv run python -m training.preparar_sprites `
  --entrada "$env:TRAPSIGHT_TRAINING_DATA_DIR" `
  --saida "$env:TRAPSIGHT_TRAINING_DATA_DIR\sprites" `
  --semente 20261021 `
  --limite-serrilhado 3.5
```

O banco exige pelo menos 300 sprites válidos e 20 insetos inteiros por grupo.
As categorias de tamanho são calculadas em tercis usando somente os insetos
inteiros; fragmentos herdam a categoria do inseto de origem. O relatório
registra fotos baixadas, recortes aceitos e descartados por motivo e sprites
por grupo e categoria.

### Conversão de COCO

1. Escolha uma fonte pública que permita o uso pretendido e forneça máscaras
   poligonais de segmentação.
2. Baixe o conjunto manualmente e selecione a exportação COCO com polígonos;
   extraia o JSON de anotações e as imagens para um diretório local.
3. Confira os termos de uso e informe a fonte e a licença identificadas ao
   executar o conversor. Ele não acessa a internet, não lê chaves e não aplica
   remoção automática de fundo: a máscara poligonal vira o canal alfa.

No PowerShell, a partir da raiz do repositório:

```powershell
cd backend
uv run python -m training.preparar_sprites `
  --entrada "$env:TRAPSIGHT_TRAINING_DATA_DIR\dataset-coco" `
  --saida "$env:TRAPSIGHT_TRAINING_DATA_DIR\sprites" `
  --fonte "https://exemplo.org/conjunto" `
  --licenca "CC-BY-4.0" `
  --semente 20261021 `
  --grupo-coco mosca
```

Se houver mais de um JSON na raiz da entrada, indique o arquivo COCO com
`--anotacoes`, usando um caminho relativo ao diretório de entrada. A saída
precisa ser nova ou estar vazia. O conversor exige ao menos 300 sprites e 20
sprites inteiros por grupo; uma execução abaixo de qualquer meta falha sem
publicar um catálogo parcial.

As categorias `pequeno`, `medio` e `grande` são atribuídas em tercis pela área
opaca dos insetos inteiros. Fragmentos herdam a categoria do sprite original.
O padrão descarta áreas menores que 100 pixels e contornos cuja razão entre
perímetro e casco convexo excede 2,0; ambos os limiares são configuráveis. A
fração padrão de fragmentos é 15% e pode ser alterada por
`--fracao-fragmentos`.

O `relatorio.json` registra fotos baixadas, recortes aceitos e descartados por
motivo, sprites por grupo e categoria e número de fragmentos. A borda do
recorte é comparada à cor de fundo estimada nas bordas da foto original.

O limite padrão de contorno é 2,0. Na coleta brasileira de 411 fotos usada
para validar este fluxo, esse valor reteve 141 insetos inteiros; o limite 3,5
reteve 325, manteve o filtro ativo e atingiu a meta de 300 sprites. O relatório
registra o valor usado; calibre-o novamente para outras fontes.

## Execução

No PowerShell, a partir da raiz do repositório:

```powershell
cd backend
uv run python -m training.gerar_dataset `
  --sprites "$env:TRAPSIGHT_TRAINING_DATA_DIR\sprites" `
  --saida "$env:TRAPSIGHT_TRAINING_DATA_DIR\dataset-sintetico" `
  --semente 20261021 `
  --idade-maxima-dias 90 `
  --quantidade 3000 `
  --largura 768 `
  --altura 576 `
  --px-por-mm 1.6 `
  --k-escala-min 1.3 `
  --k-escala-max 3.0
```

O valor `90` é apenas um exemplo de parâmetro operacional. A especificação
mantém `IDADE_MAXIMA_DIAS` pendente de calibração; substitua-o pelo limite
aprovado antes de gerar o dataset de treinamento. A idade máxima é obrigatória
na CLI para não transformar uma estimativa arbitrária em padrão do projeto.

O gerador usa sprites de insetos reais em escala física. Cada amostra sorteia
`k` em distribuição log-uniforme entre 1,3 e 3,0; o tamanho renderizado é
`tamanho_mm × px_por_mm × k × variação`, com variação entre 0,85 e 1,2.
O valor `k` e o `px_por_mm` efetivo da placa são registrados no manifesto.
O posicionamento usa um mapa de densidade com focos gaussianos, gradiente,
reforço de borda e componente uniforme. A cena tem placa creme/amarelada,
textura sutil, moldura escura, sombra de contato, iluminação, ruído e JPEG.

O alvo é sorteado em três faixas balanceadas: 0–10%, 10–20% e 20–35%.
`percentual_cobertura_real` é medido na máscara final; cada amostra registra
`alvo_atingido`, que indica erro absoluto de até 0,5 ponto percentual. Pixels
de poeira, fibras e sombras ficam fora da classe coberta.

Os pesos padrão destinam 70% das seleções a moscas, mosquitos, mariposas e
vespas; os 30% restantes cobrem formigas, baratas, besouros, psocópteros,
percevejos, cupins e grupos não classificados. Cada amostra e a configuração
global registram os pesos efetivos. Para alterá-los, informe um objeto JSON a
`--pesos-grupo`.

As probabilidades dos distratores são mantidas na constante
`FREQUENCIAS_DISTRATORES` do módulo do gerador.

Para executar novamente a mesma configuração, use a mesma semente global, o
mesmo catálogo, a mesma versão do gerador e os mesmos parâmetros. A saída deve
ser nova ou estar vazia. O diretório contém:

- `imagens/amostra_NNNNNN.png`: cenas RGB para entrada do modelo;
- `mascaras/amostra_NNNNNN.png`: rótulos 0 (fundo), 1 (placa limpa) e 2 (placa
  coberta);
- `metadados.jsonl`: uma linha por imagem, incluindo semente individual,
  cobertura-alvo e medida na máscara, `alvo_atingido`, idade, quantidade de
  sprites, `px_por_mm`, `k_escala`, pesos por grupo, distratores, dominante de
  cor e divisão treino/validação/teste;
- `configuracao.json`: parâmetros globais usados na geração.

## Dados de demonstração

O seed do backend cria seis armadilhas e seus ciclos de refil com análises e
mídias sintéticas. Execute-o explicitamente a partir de `backend`, depois de
configurar o PostgreSQL de desenvolvimento, `UPLOADS_DIR` e o banco de sprites
externo:

```powershell
cd backend
$env:TRAPSIGHT_TRAINING_DATA_DIR = "D:\dados\trapsight\treino"
uv run python -m src.seed_demo
```

O comando registra o percentual medido na máscara e imprime o alvo e o valor
persistido de cada análise. Com `STORAGE_BACKEND=filesystem`, imagens e máscaras
ficam em `UPLOADS_DIR`. Com `STORAGE_BACKEND=database`, os PNGs ficam nas colunas
`imagem_original` e `mascara`, e `caminho_imagem` guarda o identificador lógico
da imagem. O manifesto `.seed_demo_manifest.json` identifica os registros e
arquivos que podem ser substituídos por uma reexecução. Outros registros e
arquivos são preservados. Fora do desenvolvimento local, a execução exige a
confirmação explícita `--confirmar-ambiente`; o destino é exibido sem
credenciais.

## Verificações

Execute os testes e o lint a partir do diretório `backend`:

```powershell
uv run --group dev --group baseline pytest
uv run --group dev ruff check training tests
```

## Baseline OpenCV

O baseline usa um único limiar global no canal V do HSV. A calibração varre os
limiares de 0 a 255 e seleciona o que maximiza o Dice somente nas amostras de
`treino`. O arquivo `training/baseline_calibracao.json` registra o limiar, a
semente global e o SHA-256 das imagens e máscaras de treino; mantenha esse
arquivo versionado junto com a avaliação correspondente.

No dataset sintético, a máscara de classes delimita a placa para representar a
entrada pré-recortada pressuposta pelo baseline. Dentro dela, o baseline conta
como cobertura cada pixel com `V < limiar_v`. Essa regra não muda por imagem e
conta sujeira escura como cobertura, limitação esperada do método.

Na pasta `backend`, execute:

```powershell
uv run --group baseline python -m training.baseline calibrar `
  --dataset "D:\dados\trapsight\dataset-sintetico"

uv run --group baseline python -m training.baseline avaliar `
  --dataset "D:\dados\trapsight\dataset-sintetico" `
  --split teste
```

A avaliação exige que a semente e o hash do conjunto de treino coincidam com o
arquivo de calibração. O JSON de métricas é gravado no diretório do dataset como
`metricas_baseline_teste.json`; ele inclui Dice, IoU, erro absoluto médio do
percentual em pontos percentuais e acurácia do status. A calibração não lê
amostras de validação ou teste.

## Treino da U-Net

O treino segue `.context/plan/model/treino_spec.md`. O código está em
`training/treino/` (configuração, dados, aumentos, perda, modelo, métricas,
seleção do melhor ponto, loop e linha de comando) e a configuração de
referência em `training/treino/configuracao_padrao.json`.

O PyTorch com CUDA vem do grupo `treino`. No Windows, o `uv.lock` usa o índice
`cu128` do PyTorch; nas demais plataformas, o PyPI. O `backend/.venv` pode estar
inacessível; use um ambiente fora do repositório:

```powershell
$env:UV_PROJECT_ENVIRONMENT = "D:\dados\trapsight\venv-treino"
uv sync --python 3.12 --group dev --group treino
```

Na pasta `backend`, com esse ambiente:

```powershell
# confirma a GPU e a memória de vídeo
uv run python -m training.treino gpu

# E0, teste de fumaça (não é resultado): 1000 imagens, 5 épocas
uv run python -m training.treino treinar --nome e0 --epocas 5 `
  --limite-treino 1000 --limite-validacao 150

# treino completo, com os valores de configuracao_padrao.json
uv run python -m training.treino treinar --nome padrao

# compara duas execuções por época (prova de reprodutibilidade)
uv run python -m training.treino comparar --a <pasta-a> --b <pasta-b>

# mede o teste, uma vez por checkpoint
uv run python -m training.treino avaliar-teste --execucao <pasta>
```

Cada execução grava em `D:\dados\trapsight\execucoes\<data>-<nome>`, fora do
repositório: `execucao.json` (sementes, hash do dataset, hiperparâmetros,
bibliotecas, hardware e `modelo_versao`), `metricas_por_epoca.csv`,
`metricas_validacao.jsonl` e os checkpoints `melhor.pt`, `melhor_dice.pt` e
`ultimo.pt`. O treino recusa começar se o dataset repetir sementes entre
conjuntos, tiver faixas de cobertura desbalanceadas, correlação entre idade e
cobertura acima de 0,1 ou máscara que não confira com os metadados. O conjunto
de teste só é aberto por `avaliar-teste`.

Os testes de `tests/training/treino/` precisam do grupo `treino` e são
ignorados sem ele. Rode-os com o ambiente acima e, se o diretório temporário
padrão estiver sem permissão, com `--basetemp` apontando para uma pasta sua.

