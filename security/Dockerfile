# Executor da suíte caixa-preta com as dependências já instaladas.
# Permite rodar em redes sem acesso à internet (por exemplo, a rede interna do Compose).
FROM python:3.12.12-slim-bookworm
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt
WORKDIR /sec
