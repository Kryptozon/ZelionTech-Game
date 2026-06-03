# ---------- Stage 1: build the Mini App frontend ----------
FROM node:20-alpine AS frontend
WORKDIR /fe
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build      # outputs /fe/dist (base=/app/)

# ---------- Stage 2: Python bot + API + static ----------
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Drop the built Mini App where the server expects it (FRONTEND_DIST=frontend/dist).
COPY --from=frontend /fe/dist ./frontend/dist

CMD ["python", "-m", "bot.main"]
