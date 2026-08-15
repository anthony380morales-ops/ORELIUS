# ORELIUS — single-container image (frontend + backend on one HTTPS service).
# Works on any free Docker host (Render, Koyeb, Fly.io, etc.).

# ---- Stage 1: build the frontend (the phone app) ----
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: backend + serve the built frontend ----
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
# Drop the built SPA where FastAPI serves it (see STATIC_DIR in app/main.py)
COPY --from=web /web/dist ./static

RUN mkdir -p logs
ENV STATIC_DIR=/app/static

EXPOSE 8000
# Bind to the platform's $PORT if provided (Render/Koyeb), else 8000.
CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
