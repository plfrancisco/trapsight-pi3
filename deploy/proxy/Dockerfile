# Imagem de produção do frontend: build estático servido pelo Caddy (proxy reverso).
# Contexto: raiz do repositório (ver .dockerignore).

FROM node:24.11-slim AS build
WORKDIR /app
RUN chown node:node /app
USER 1000:1000

COPY --chown=node:node frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY --chown=node:node frontend/ ./
# Mesma origem em produção: a API fica em /api, atrás do proxy.
ENV VITE_API_URL=/api \
    VITE_AUTENTICACAO_ATIVA=true
RUN npm run build

FROM caddy:2.10.2-alpine
COPY --from=build /app/dist /srv
COPY deploy/proxy/Caddyfile /etc/caddy/Caddyfile
# Usuário sem privilégios; os volumes de estado herdam este dono na primeira criação.
# O binário vem com capacidade de arquivo para portas baixas, que não funciona com
# `no-new-privileges` e sem capacidades; o compose libera as portas por sysctl.
RUN apk add --no-cache libcap-utils \
    && setcap -r /usr/bin/caddy \
    && apk del libcap-utils \
    && mkdir -p /data /config && chown 65532:65532 /data /config
USER 65532:65532
