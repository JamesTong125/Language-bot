FROM node:24-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 3000

# Development server. node_modules lives in a named volume, so reinstall if the lockfile changed.
CMD ["sh", "-c", "npm ci --prefer-offline --no-audit --no-fund && npm run dev -- --hostname 0.0.0.0 --port 3000"]
