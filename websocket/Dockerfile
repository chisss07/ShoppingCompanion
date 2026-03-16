# ============================================================
# Shopping Companion - WebSocket Server Dockerfile
# Multi-stage build: builder installs deps, runtime is lean
# ============================================================

# ── Stage 1: Builder ────────────────────────────────────────
FROM python:3.13-slim-bookworm AS builder

WORKDIR /build

# uvicorn[standard] pulls in uvloop and httptools which need a C compiler
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create a virtual environment so we can copy it cleanly to runtime
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install Python dependencies first (layer cache friendly)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Stage 2: Runtime ────────────────────────────────────────
FROM python:3.13-slim-bookworm AS runtime

# curl is needed for the Docker/Compose health check probe
RUN apt-get update && apt-get install -y --no-install-recommends \
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

EXPOSE 8001

# Health check against our /health endpoint
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Single uvicorn worker: pub/sub state lives in-process, so multiple
# workers would each need their own Redis subscription. Scale horizontally
# by adding more container replicas behind a sticky-session load balancer.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
