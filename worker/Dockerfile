# ============================================================
# Shopping Companion - Celery Worker Dockerfile
# Multi-stage build: builder installs deps, runtime is lean
# ============================================================

# ── Stage 1: Builder ────────────────────────────────────────
FROM python:3.12-slim-bookworm AS builder

WORKDIR /build

# Build dependencies required by gevent and asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libev-dev \
    && rm -rf /var/lib/apt/lists/*

# Create a virtual environment so we can copy it cleanly to runtime
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies first (layer cache friendly)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Stage 2: Runtime ────────────────────────────────────────
FROM python:3.12-slim-bookworm AS runtime

# Runtime OS libraries: libpq for asyncpg, curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the virtualenv from the builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create a non-root user for security
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

WORKDIR /app

# Copy application source with correct ownership
COPY --chown=appuser:appuser . .

# Drop to non-root user
USER appuser

CMD ["celery", "-A", "app.celery_app", "worker", "--loglevel=info", "--concurrency=4", "--pool=gevent", "-Q", "search,default"]
