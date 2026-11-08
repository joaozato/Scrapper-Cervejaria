# Estágio 1: Compilar o frontend React
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Estágio 2: Preparar o backend FastAPI
FROM python:3.11-slim
WORKDIR /app/backend

# Instalar dependências de compilação essenciais para o PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependências do Python
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers and OS dependencies
RUN playwright install chromium
RUN playwright install-deps

# Copiar os arquivos do backend
COPY backend/app ./app

# Copiar os arquivos compilados do frontend do Estágio 1
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# O Railway define a variável de ambiente PORT automaticamente
ENV PORT=8000
EXPOSE 8000

# Iniciar o servidor ASGI Uvicorn de dentro de /app/backend
CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
