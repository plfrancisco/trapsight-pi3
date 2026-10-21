# Gerador de dataset sintético

O gerador cria cenas de refis adesivos, máscaras semânticas e metadados a
partir de um catálogo local de sprites PNG com transparência e licença
registrada. Os artefatos gerados devem ficar fora do código-fonte versionado.

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
  --quantidade 3000
```

O valor `90` é apenas um exemplo de parâmetro operacional. A especificação
mantém `IDADE_MAXIMA_DIAS` pendente de calibração; substitua-o pelo limite
aprovado antes de gerar o dataset de treinamento. A idade máxima é obrigatória
na CLI para não transformar uma estimativa arbitrária em padrão do projeto.

O gerador permite até 2400 tentativas de composição por imagem para que alvos
altos não parem prematuramente. Esse número é um teto de segurança; a composição
encerra quando a máscara fica dentro da tolerância de 2 pontos percentuais ou
quando atinge esse limite de tentativas.

Os pesos padrão distribuem 70% das seleções entre moscas, mosquitos e
mariposas, e 30% entre formigas, baratas e besouros. Cada linha de amostra e
a configuração global registram os pesos efetivos. Para alterá-los, informe
um objeto JSON a --pesos-grupo.

O alvo de cobertura é sorteado uniformemente dentro de uma das três faixas, com
um terço das amostras por faixa. Isso implementa a estratificação da seção 7.1;
a distribuição marginal não é uniforme em `[0, 100]`, embora a seção 4.3 também
peça amostragem uniforme nesse intervalo. As duas exigências são incompatíveis
no mesmo dataset, então o gerador segue a proporção estratificada mais específica.

As probabilidades dos distratores são mantidas na constante
`FREQUENCIAS_DISTRATORES` do módulo do gerador.

Para executar novamente a mesma configuração, use a mesma semente global, o
mesmo catálogo, a mesma versão do gerador e os mesmos parâmetros. A saída deve
ser nova ou estar vazia. O diretório contém:

- `imagens/amostra_NNNNNN.png`: cenas RGB para entrada do modelo;
- `mascaras/amostra_NNNNNN.png`: rótulos 0 (fundo), 1 (placa limpa) e 2 (placa
  coberta);
- `metadados.jsonl`: uma linha por imagem, incluindo semente individual,
  cobertura medida na máscara, idade, quantidade de sprites, distratores,
  dominante de cor e divisão treino/validação/teste;
- `configuracao.json`: parâmetros globais usados na geração.

## Verificações

Execute os testes e o lint a partir do diretório `backend`:

```powershell
uv run pytest
uv run ruff check training tests
```
