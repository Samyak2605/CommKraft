# Build frontend (Vite outputs to ../backend/static)
FROM node:20-alpine AS frontend
WORKDIR /app
COPY frontend/ ./frontend/
WORKDIR /app/frontend
RUN npm ci && npm run build

# Backend + static
FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m spacy download en_core_web_md
COPY backend/ ./backend
COPY --from=frontend /app/backend/static ./backend/static
ENV PYTHONPATH=/app/backend
WORKDIR /app/backend
EXPOSE 8000
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT
