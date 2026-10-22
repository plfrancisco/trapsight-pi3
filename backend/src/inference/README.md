# Inferência da placa

O backend carrega o checkpoint indicado por `MODEL_WEIGHTS_PATH` durante a
inicialização. O modo padrão é `modelo`; a aplicação não inicia quando os pesos
ou os metadados não correspondem ao pipeline de treino.

Para desenvolvimento sem pesos, defina `INFERENCE_MODE=stub` explicitamente.
O modo `modelo` executa em CPU. `INFERENCE_THREADS` limita as threads usadas pelo
PyTorch e assume o valor `1` quando não configurado.

Instale as dependências opcionais usadas para executar os testes do modelo com:

```sh
uv sync --group inference
```

A inferência mantém a orientação dos pixels gravados e ignora a orientação EXIF.
O pipeline de treino não aplica a transformação EXIF; manter a mesma convenção
evita que o modelo receba imagens em uma orientação diferente da vista no treino.
