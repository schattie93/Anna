# Ein Container für Backend + gebaute Weboberfläche (spart RAM auf dem NAS).
# Alle Basis-Images gibt es für amd64 und arm64.

FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PHYSIOFLOW_FRONTEND_DIST=/app/frontend
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend /build/dist ./frontend
RUN useradd --system --uid 1000 physioflow
USER physioflow
EXPOSE 8000
# Datenbank-Migrationen beim Start anwenden, dann Server starten
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
