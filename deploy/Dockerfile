# ============================================================
# Shopping Companion — Combined Single-Container Image
# Runs nginx + backend + websocket + celery worker together
# via supervisord. Only postgres and redis remain separate.
# ============================================================

# ── Stage 1: Build React frontend ───────────────────────────
FROM node:22-alpine AS frontend-build

WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# ── Stage 2: Build Python virtualenv ────────────────────────
FROM python:3.12-slim-bookworm AS python-build

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libev-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY deploy/requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Stage 3: Runtime ────────────────────────────────────────
FROM python:3.12-slim-bookworm AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Python venv from builder
COPY --from=python-build /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Built React app
COPY --from=frontend-build /app/dist /usr/share/nginx/html

# Nginx config (uses localhost instead of container hostnames)
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
RUN rm -f /etc/nginx/sites-enabled/default

# Supervisord config
COPY deploy/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Application source — each service in its own subdirectory
COPY backend/ /app/backend/
COPY worker/  /app/worker/
COPY websocket/ /app/websocket/

EXPOSE 80

HEALTHCHECK --interval=20s --timeout=10s --start-period=90s --retries=5 \
    CMD curl -f http://localhost/api/health || exit 1

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
