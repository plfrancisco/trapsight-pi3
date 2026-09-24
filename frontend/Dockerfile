FROM node:24-slim

WORKDIR /app
RUN chown node:node /app

USER node

# FE01 fornecerá package.json e package-lock.json para npm ci.
COPY --chown=node:node package.json package-lock.json ./
RUN npm ci

COPY --chown=node:node . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
