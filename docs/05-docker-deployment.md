# Docker Deployment Architecture: AI-Powered Shopping Companion

## Document Information

- **Project:** ShoppingCompanion
- **Version:** 1.0
- **Date:** March 15, 2026
- **Scope:** Container orchestration design for all application services

---

## 1. Architecture Overview

The Shopping Companion application is decomposed into six containerized services organized across three isolated Docker networks. The architecture enforces a strict separation between public-facing, application-layer, and data-layer concerns, preventing lateral movement and reducing blast radius in the event of a service compromise.

The six services are:

- **frontend** — React application served by nginx; the sole public ingress point
- **backend** — FastAPI REST API; handles business logic and coordinates downstream services
- **search-worker** — Python AI service for product search; communicates via internal RPC and Redis pub/sub
- **websocket** — WebSocket server delivering real-time updates to clients
- **postgres** — PostgreSQL 16 database; only reachable from the data network
- **redis** — Redis 7 cache and pub/sub broker; only reachable from the data network

---

## 2. Network Topology

Three bridge networks partition the service graph. No service spans all three layers; each service is attached only to the networks required for its direct communication paths.

### 2.1 Network Definitions

**frontend-net**

- Type: bridge
- Attached services: frontend, backend, websocket
- Purpose: carries HTTP/WebSocket traffic between the nginx reverse proxy and application services
- No direct database or cache access permitted from this network

**backend-net**

- Type: bridge
- Attached services: backend, search-worker, websocket, redis
- Purpose: internal RPC calls between Python services and Redis pub/sub messaging
- Isolated from public ingress; frontend cannot reach search-worker or redis directly

**data-net**

- Type: bridge
- Attached services: backend, postgres, redis
- Purpose: database connections and cache reads/writes
- Accessible only to backend; search-worker reads from redis via backend-net, not data-net

### 2.2 Network Attachment Matrix

| Service | frontend-net | backend-net | data-net |
|---|---|---|---|
| frontend | Yes | No | No |
| backend | Yes | Yes | Yes |
| search-worker | No | Yes | No |
| websocket | Yes | Yes | No |
| postgres | No | No | Yes |
| redis | No | Yes | Yes |

### 2.3 Port Mapping Strategy

Only the frontend service exposes ports on the host interface. All other services communicate exclusively over internal Docker networks.

- **Production:** frontend binds host port 80 (HTTP) and 443 (HTTPS) to the nginx container
- **Development:** frontend maps host port 3000 for the React dev server and 8080 for a direct backend passthrough for tooling convenience
- All inter-service communication uses Docker's internal DNS by service name (e.g., `http://backend:8000`, `redis://redis:6379`)
- postgres listens only on data-net at its default port 5432; no host binding in any environment
- redis listens only on backend-net and data-net at port 6379; no host binding in production

### 2.4 SSL/TLS Termination

TLS termination occurs at the nginx container boundary in production. nginx holds the TLS certificates (mounted as a read-only volume) and terminates HTTPS before proxying plain HTTP to backend and WebSocket services on the internal network. No internal service-to-service communication uses TLS; the network isolation boundary is treated as the trust boundary for inter-service traffic.

In a cloud deployment, this nginx TLS termination may be replaced or preceded by a cloud load balancer (ALB, GCP HTTPS LB), in which case nginx handles only internal routing.

---

## 3. Volume Strategy

### 3.1 Named Volumes (Persistent Data)

**postgres-data**

- Mounted at: `/var/lib/postgresql/data` inside the postgres container
- Driver: local (default)
- Purpose: all PostgreSQL WAL and table data
- Backup strategy: this volume is the target for scheduled `pg_dump` operations; consider a sidecar or scheduled job writing dumps to an object store
- Never deleted during `docker compose down`; requires explicit `docker compose down -v` to remove

**redis-data**

- Mounted at: `/data` inside the redis container
- Driver: local
- Purpose: Redis AOF persistence file
- redis is configured with `appendonly yes` so restart survivability is maintained
- Size bounded by application cache patterns; monitor for unbounded growth if eviction is not configured

### 3.2 Bind Mounts (Configuration, Certificates)

**nginx-config**

- Host path: `./config/nginx/` (repository-tracked)
- Container path: `/etc/nginx/conf.d/` (read-only)
- Contains: virtual host configuration, proxy pass rules, upstream definitions

**tls-certs**

- Host path: `/etc/letsencrypt/live/yourdomain.com/` or a secrets-managed path
- Container path: `/etc/ssl/certs/app/` (read-only)
- Never committed to source control; provisioned by certbot or a secrets manager at deploy time

**shared-config**

- Host path: `./config/shared/`
- Container path: `/app/config/` (read-only)
- Purpose: non-secret application configuration shared between backend and search-worker (feature flags, model configuration parameters, category taxonomies)

### 3.3 Ephemeral Storage

- search-worker requires a writable temporary directory for model artifact caching during startup; this is an anonymous volume at `/tmp/model-cache` scoped to the container lifecycle
- All other application containers operate with read-only root filesystems (see Section 5.3)

---

## 4. Service Definitions

### 4.1 frontend

**Image strategy:** custom build from repository source

**Build context:** `./frontend/`

**Dockerfile:** `./frontend/Dockerfile`

The build uses two stages. The first stage (builder) installs Node.js dependencies and runs the production build. The second stage is a hardened nginx image that copies only the compiled static assets from the builder stage. The resulting image contains no Node.js runtime, no source code, and no build tooling.

**Base images:**
- Builder stage: `node:22-alpine` — minimal Alpine-based Node image for the build step
- Final stage: `nginx:1.27-alpine` — Alpine-based nginx for the runtime image

**Key configuration:**
- nginx serves the React app from `/usr/share/nginx/html/`
- nginx proxies `/api/` to the backend service and `/ws/` to the websocket service using the internal DNS names
- nginx enforces `try_files $uri /index.html` for client-side routing
- Health check: HTTP GET to `/healthz` (a static file included in the build output) every 30 seconds

**Resource limits (production):**
- Memory: 256MB limit, 128MB reservation
- CPU: 0.5 cores

**Restart policy:** `unless-stopped`

**Networks:** frontend-net

---

### 4.2 backend

**Image strategy:** custom build from repository source

**Build context:** `./backend/`

**Dockerfile:** `./backend/Dockerfile`

Multi-stage Python build. The builder stage installs all dependencies including build tools using a full slim image. The final stage copies only the installed packages and application source from the builder, keeping the runtime image free of compilers and build dependencies.

**Base images:**
- Builder stage: `python:3.13-slim-bookworm`
- Final stage: `python:3.13-slim-bookworm`

**Application server:** Uvicorn with multiple workers managed by a process supervisor or native Uvicorn multi-process mode. The number of workers is controlled by an environment variable (`UVICORN_WORKERS`, default 4) to allow easy tuning without rebuilding the image.

**Key configuration:**
- Listens on `0.0.0.0:8000` within the container
- Alembic database migrations run as an init step via a separate short-lived container or an entrypoint guard that checks migration state before starting the server
- Connects to postgres via `data-net` and to redis via `data-net` for cache operations and via `backend-net` for pub/sub publication
- Health check: HTTP GET to `/health` every 20 seconds; the endpoint checks database connectivity and redis connectivity before returning 200

**Resource limits (production):**
- Memory: 1GB limit, 512MB reservation
- CPU: 2.0 cores

**Restart policy:** `unless-stopped`

**Networks:** frontend-net, backend-net, data-net

---

### 4.3 search-worker

**Image strategy:** custom build from repository source

**Build context:** `./search-worker/`

**Dockerfile:** `./search-worker/Dockerfile`

Python service optimized for AI workload. The image must accommodate large ML model dependencies (e.g., sentence-transformers, FAISS, torch). The builder stage installs all Python packages. The final stage copies the environment. Model weights are not baked into the image; they are downloaded or mounted at startup from a model registry or volume.

**Base images:**
- Builder stage: `python:3.13-slim-bookworm`
- Final stage: `python:3.13-slim-bookworm`

**Key configuration:**
- Does not expose any HTTP port; communicates exclusively via Redis pub/sub and direct Redis data structures on backend-net
- Subscribes to a Redis channel for incoming search job requests published by the backend
- Publishes results back to Redis, where backend retrieves and returns them to the client
- Writable volume at `/tmp/model-cache` for downloaded model artifacts; this directory is populated on first start and persists in an anonymous volume for container lifetime
- `PYTHONDONTWRITEBYTECODE=1` and `PYTHONUNBUFFERED=1` set at build time
- Health check: a custom Python health script that verifies the Redis subscription is active and the model is loaded

**Resource limits (production):**
- Memory: 4GB limit, 2GB reservation (AI model workload)
- CPU: 4.0 cores
- If GPU acceleration is required, the resource specification includes an NVIDIA device request (documented separately in the GPU variant section)

**Restart policy:** `on-failure` with max 5 retries (model loading failures should not cause infinite restart loops)

**Networks:** backend-net

---

### 4.4 websocket

**Image strategy:** custom build from repository source

**Build context:** `./websocket/`

**Dockerfile:** `./websocket/Dockerfile`

Python service running an async WebSocket server (FastAPI with WebSocket support or a dedicated framework such as Starlette). Subscribes to Redis pub/sub on backend-net to receive events and pushes them to connected browser clients via the nginx proxy on frontend-net.

**Base images:**
- Builder stage: `python:3.13-slim-bookworm`
- Final stage: `python:3.13-slim-bookworm`

**Key configuration:**
- Listens on `0.0.0.0:8001` within the container
- nginx proxies WebSocket upgrade requests from `/ws/` to this service; nginx configuration must include `proxy_http_version 1.1` and `Upgrade`/`Connection` header forwarding
- Subscribes to relevant Redis channels to push price alerts, search result notifications, and system events to connected clients
- Stateless at the application level; client session state is managed via token validation against the backend on connect
- Health check: custom TCP probe on port 8001 every 15 seconds

**Resource limits (production):**
- Memory: 512MB limit, 256MB reservation
- CPU: 1.0 core

**Restart policy:** `unless-stopped`

**Networks:** frontend-net, backend-net

---

### 4.5 postgres

**Image strategy:** official image, no custom build

**Image:** `postgres:16-alpine`

No custom Dockerfile. All configuration is supplied via environment variables and a mounted initialization script directory.

**Key configuration:**
- Data volume: `postgres-data` mounted at `/var/lib/postgresql/data`
- Initialization scripts: `./config/postgres/init/` mounted at `/docker-entrypoint-initdb.d/` (read-only); these scripts run once on first startup to create application databases and roles
- postgres.conf tuning parameters (shared_buffers, work_mem, max_connections) are supplied via the `POSTGRES_*` environment variables or a mounted `postgresql.conf` file rather than baked into a custom image, keeping the upgrade path clean
- Health check: `pg_isready -U $POSTGRES_USER -d $POSTGRES_DB` every 10 seconds with a 5-second timeout and 5 retries before declaring unhealthy

**Resource limits (production):**
- Memory: 2GB limit, 1GB reservation
- CPU: 2.0 cores

**Restart policy:** `unless-stopped`

**Networks:** data-net

---

### 4.6 redis

**Image strategy:** official image, no custom build

**Image:** `redis:7-alpine`

**Key configuration:**
- Launched with the command `redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru`
- `appendonly yes` enables AOF persistence; the AOF file lives in the `redis-data` volume at `/data`
- `maxmemory` and eviction policy prevent unbounded memory growth; `allkeys-lru` suits the cache-heavy workload
- No authentication configured by default in the design; for production, `requirepass` should be set via environment variable injection with a secret from a vault or environment file
- Health check: `redis-cli ping` every 10 seconds

**Resource limits (production):**
- Memory: 768MB limit, 512MB reservation (headroom above the 512MB maxmemory to allow AOF buffer)
- CPU: 0.5 cores

**Restart policy:** `unless-stopped`

**Networks:** backend-net, data-net

---

## 5. Dockerfile Design Specifications

### 5.1 Frontend Dockerfile (Multi-Stage)

**Stage 1 — builder**

- Base: `node:22-alpine`
- Working directory: `/build`
- Copy `package.json` and `package-lock.json` first, then run `npm ci --omit=dev` before copying application source; this ordering ensures the dependency installation layer is cached across commits that only change source files
- Set `NODE_ENV=production` as a build ARG so any build-time NODE_ENV checks resolve correctly
- Run `npm run build` to produce the static asset bundle in `/build/dist`
- No artifacts other than `/build/dist` leave this stage

**Stage 2 — runtime**

- Base: `nginx:1.27-alpine`
- Copy `/build/dist` from the builder stage into `/usr/share/nginx/html/`
- Copy nginx configuration from the build context into `/etc/nginx/conf.d/default.conf`
- Remove the default nginx `conf.d` sample files that ship with the base image
- Expose port 80 (and 443 when TLS is terminated at this layer)
- Run as a non-root user: nginx is configured to run worker processes as the `nginx` user (already non-root in the Alpine image); the master process requires root briefly to bind port 80 but can be configured to drop privileges immediately
- HEALTHCHECK instruction: `curl -f http://localhost/healthz || exit 1` every 30 seconds

**Layer cache optimization:** the separation of `package.json` copy and `npm ci` from application source copy is the most impactful caching decision; a code-only change rebuilds only the final two layers.

---

### 5.2 Python Service Dockerfiles (backend, search-worker, websocket)

All three Python services share the same structural Dockerfile pattern with service-specific variations in the packages installed.

**Stage 1 — builder**

- Base: `python:3.13-slim-bookworm`
- Install system build dependencies (`gcc`, `libpq-dev` for psycopg2, and any service-specific native libraries) in a single `apt-get install` layer; clean apt cache in the same layer to avoid bloat
- Create and activate a virtual environment at `/opt/venv` using `python -m venv`; all pip operations target this venv
- Copy `requirements.txt` before application source to maximize pip install layer cache hits
- Run `pip install --no-cache-dir -r requirements.txt` with the venv active
- The `--no-cache-dir` flag prevents pip's HTTP cache from inflating the image; the layer cache itself provides equivalent benefits for repeated builds

**Stage 2 — runtime**

- Base: `python:3.13-slim-bookworm` (same base as builder; in production, consider `gcr.io/distroless/python3-debian12` for further attack surface reduction)
- Install only runtime system libraries (not build tools); for psycopg2, this is `libpq5`, not `libpq-dev`
- Copy `/opt/venv` from the builder stage
- Set `PATH` to include `/opt/venv/bin` so the venv Python and all installed scripts are used without activation
- Copy application source into `/app/`
- Create a non-root user and group (`appuser`, UID 1000) and `chown /app` to that user
- Switch to `appuser` with the `USER` instruction before the final `CMD`
- Set `PYTHONDONTWRITEBYTECODE=1` and `PYTHONUNBUFFERED=1` as ENV instructions

**search-worker variation:**

- The builder stage must include additional native libraries for AI dependencies (potentially `libgomp1` for OpenMP, `libblas-dev` for numerical libraries)
- The final image for search-worker will be substantially larger than backend or websocket due to PyTorch or similar ML framework dependencies; this is acceptable given the workload, but the multi-stage pattern still eliminates compilers and build headers from the final image
- Model weights must not be `COPY`-ed into the image; a startup script handles model download or reads from a mounted volume

---

### 5.3 Security Hardening Specifications

The following hardening measures apply across all custom-built service images.

**Non-root execution**

Every application container runs as a dedicated non-root user with a fixed UID (1000 for application services). The user is created in the Dockerfile. The `USER` instruction is the last configuration step before `CMD`/`ENTRYPOINT`. No `sudo` or privilege escalation capability is installed.

**Read-only root filesystem**

- frontend (nginx), backend, and websocket containers declare a read-only root filesystem via the Docker Compose `read_only: true` service property
- Writable tmpfs mounts are added for directories that require runtime writes: nginx needs `/var/cache/nginx`, `/var/run`, and `/tmp`; Python services need `/tmp`
- search-worker uses a writable anonymous volume at `/tmp/model-cache` rather than a read-only root, given the model artifact download requirement

**Capability restrictions**

All services drop all Linux capabilities (`cap_drop: ALL`) and add back only the minimum required. The frontend nginx container adds back `NET_BIND_SERVICE` to bind port 80 without root; all Python services require no capabilities beyond the dropped-all baseline.

**No new privileges**

The `no-new-privileges: true` security option is set on all service definitions, preventing privilege escalation via setuid binaries.

**Minimal base images**

All custom images use `slim` or `alpine` variants. The attack surface of the final runtime image contains no package managers, compilers, shells (where distroless is used), or documentation.

---

## 6. Environment Variable Management

### 6.1 File Structure

The environment configuration uses a layered `.env` file approach.

**`.env`** (git-ignored, required at deploy time)

Contains all secrets and environment-specific values: database passwords, Redis passwords, API keys for external shopping data providers, JWT signing secrets, AI model API tokens. This file is never committed. A `.env.example` file with placeholder values and documentation comments is committed in its place.

**`.env.defaults`** (git-tracked)

Contains non-secret default values shared across environments: application name, default pagination sizes, feature flag defaults, log level defaults, Redis TTL defaults. Services reference these via `env_file` in the Compose definition.

**`.env.production`** (git-tracked, no secrets)

Overrides defaults for production-specific non-secret configuration: `LOG_LEVEL=warning`, `DEBUG=false`, worker count settings, timeout values.

**`.env.development`** (git-tracked, no secrets)

Overrides for development: `LOG_LEVEL=debug`, `DEBUG=true`, hot reload flags, reduced worker counts.

### 6.2 Variable Injection Pattern

Each service's Compose definition lists an `env_file` array in order of precedence (last file wins for duplicate keys):

1. `.env.defaults`
2. `.env.production` or `.env.development` depending on compose file variant
3. `.env` (secrets, overrides everything)

Individual `environment` keys in the Compose service definition are used only for values that are computed from other variables (e.g., constructing a `DATABASE_URL` from component parts) or for values that differ per-container when the same image runs multiple instances.

### 6.3 Secret Variables per Service

**postgres:** `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`

**redis:** `REDIS_PASSWORD` (passed as the `requirepass` argument)

**backend:** `DATABASE_URL` (assembled from postgres credentials), `REDIS_URL`, `JWT_SECRET_KEY`, `AI_SEARCH_API_KEY`, `ALLOWED_ORIGINS`

**search-worker:** `REDIS_URL`, `MODEL_API_KEY`, `MODEL_REGISTRY_URL`

**websocket:** `REDIS_URL`, `JWT_SECRET_KEY` (for validating tokens on connect), `ALLOWED_ORIGINS`

**frontend:** build-time only; `REACT_APP_API_BASE_URL` and `REACT_APP_WS_URL` are baked into the static build via `ARG` instructions and are not secret

---

## 7. Dependency Ordering and Health Checks

### 7.1 Startup Dependency Graph

The correct startup sequence is enforced via `depends_on` with `condition: service_healthy` rather than `condition: service_started`. Using `service_started` only guarantees the container process has launched, not that the service is ready to accept connections.

The dependency graph is:

```
postgres (no dependencies)
redis (no dependencies)
backend (depends on: postgres healthy, redis healthy)
search-worker (depends on: redis healthy)
websocket (depends on: redis healthy, backend healthy)
frontend (depends on: backend healthy)
```

### 7.2 Health Check Specifications per Service

**postgres**

- Test: `pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}`
- Interval: 10 seconds
- Timeout: 5 seconds
- Retries: 5
- Start period: 30 seconds (allows initialization scripts to complete on first run)

**redis**

- Test: `redis-cli ping`
- Interval: 10 seconds
- Timeout: 3 seconds
- Retries: 3
- Start period: 10 seconds

**backend**

- Test: `curl -f http://localhost:8000/health`
- Interval: 20 seconds
- Timeout: 10 seconds
- Retries: 5
- Start period: 60 seconds (allows database migrations to run on startup)

**search-worker**

- Test: custom Python health script at `/app/healthcheck.py` that verifies Redis subscription and model load status
- Interval: 30 seconds
- Timeout: 15 seconds
- Retries: 3
- Start period: 120 seconds (model download and loading can take significant time on cold start)

**websocket**

- Test: `curl -f http://localhost:8001/health` (a minimal HTTP endpoint alongside the WebSocket server)
- Interval: 15 seconds
- Timeout: 5 seconds
- Retries: 3
- Start period: 30 seconds

**frontend**

- Test: `curl -f http://localhost/healthz`
- Interval: 30 seconds
- Timeout: 5 seconds
- Retries: 3
- Start period: 15 seconds

---

## 8. Production vs Development Configuration

### 8.1 docker-compose.yml (Production)

The production Compose file is the canonical definition of all services. It contains:

- All service definitions with production base images and build configurations
- Full resource limits and reservations for all services
- `restart: unless-stopped` for stable services; `restart: on-failure` with `max_attempts` for search-worker
- All three network definitions with `driver: bridge`
- All named volume definitions
- `read_only: true` on applicable containers
- `no-new-privileges: true` on all services
- `cap_drop: ALL` with selective `cap_add` per service
- Health checks fully configured with production-appropriate intervals
- env_file references to `.env.defaults`, `.env.production`, and `.env`
- Log driver configuration (see Section 9)

### 8.2 docker-compose.dev.yml (Development)

The development Compose file is used with `docker compose -f docker-compose.yml -f docker-compose.dev.yml up`. It overrides and extends the production definition for developer ergonomics.

**frontend overrides:**

- Replaces the nginx image with the Node dev server (`node:22-alpine` running `npm start`)
- Mounts `./frontend/src` as a bind mount into the container for hot module replacement
- Maps host port 3000 to container port 3000
- Adds `WATCHPACK_POLLING=true` and `CHOKIDAR_USEPOLLING=true` environment variables for file watch compatibility on macOS and Windows host mounts

**backend overrides:**

- Mounts `./backend/app` as a bind mount to `/app/app/` for live code reload
- Replaces the production `CMD` with `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- Maps host port 8000 to container port 8000 for direct API access during development
- Maps host port 5678 for debugpy remote debugging attachment
- Sets `LOG_LEVEL=debug`
- Removes resource limits (developers may have varying machine specs)

**search-worker overrides:**

- Mounts `./search-worker` as a bind mount for live reload
- Maps host port 5679 for debugpy
- May use a lighter mock model in development by setting `USE_MOCK_MODEL=true`

**websocket overrides:**

- Mounts `./websocket` as a bind mount
- Maps host port 8001 for direct WebSocket testing
- Maps host port 5680 for debugpy

**postgres overrides:**

- Maps host port 5432 for direct psql and GUI tool access (pgAdmin, TablePlus)
- No resource limits applied

**redis overrides:**

- Maps host port 6379 for direct redis-cli and GUI access (RedisInsight)
- No resource limits applied

**General development overrides:**

- `read_only: false` on all services (bind mounts require writability)
- `PYTHONDONTWRITEBYTECODE` is still set, but write access is allowed for the app directory
- All capability restrictions remain in place (security practices should be tested in development)

### 8.3 docker-compose.override.yml Strategy

The `docker-compose.override.yml` file is git-ignored and is the correct location for individual developer customizations that should not be shared:

- Binding additional debug ports
- Swapping in personal API keys for local testing
- Mounting a local checkout of a shared library package
- Enabling additional logging verbosity for a specific service
- Running with a personal fork of an image

A `docker-compose.override.yml.example` is committed to the repository documenting common override patterns with inline comments.

When running `docker compose up` without specifying files, Docker automatically merges `docker-compose.yml` and `docker-compose.override.yml`. Developers who want the development profile run `docker compose -f docker-compose.yml -f docker-compose.dev.yml up`, which loads the override on top if it also exists.

---

## 9. Resource Management

### 9.1 Memory and CPU Limits Summary

| Service | Memory Limit | Memory Reservation | CPU Limit | CPU Reservation |
|---|---|---|---|---|
| frontend | 256MB | 128MB | 0.50 | 0.25 |
| backend | 1024MB | 512MB | 2.00 | 1.00 |
| search-worker | 4096MB | 2048MB | 4.00 | 2.00 |
| websocket | 512MB | 256MB | 1.00 | 0.50 |
| postgres | 2048MB | 1024MB | 2.00 | 1.00 |
| redis | 768MB | 512MB | 0.50 | 0.25 |
| **Total** | **~8.6GB** | **~4.4GB** | **10.00** | **5.00** |

Reservations represent the minimum guaranteed allocation; limits represent the hard ceiling. On a host with 16GB RAM and 8 CPU cores, these limits provide comfortable headroom. Adjust search-worker limits based on the specific model loaded.

### 9.2 Restart Policies

**`unless-stopped`** — frontend, backend, websocket, postgres, redis

These services should always be running; they are restarted on failure, on daemon restart, but not when explicitly stopped by an operator.

**`on-failure` with `max_attempts: 5`** — search-worker

The search-worker may fail during model loading due to memory constraints or network issues downloading model artifacts. Capping retries prevents a misconfigured worker from consuming resources in a crash loop. After 5 failures, the container remains stopped and requires operator intervention.

### 9.3 Log Management

All containers use the `json-file` log driver with rotation configured to prevent unbounded disk consumption.

Log driver configuration applied to all services:

- Driver: `json-file`
- `max-size`: 50MB per file
- `max-file`: 5 files retained (250MB maximum per service)

For production deployments feeding into a centralized log aggregation platform (ELK, Datadog, CloudWatch), the log driver is replaced with the appropriate driver (`awslogs`, `fluentd`, `gelf`) and the rotation configuration moves to the aggregator. The Compose file centralizes this in an `x-logging` YAML extension field that is anchored and merged into each service definition, ensuring consistency and single-point configuration.

Search-worker logs are structured JSON output (`structlog` or equivalent) to enable log parsing for model performance metrics and search latency tracking.

---

## 10. Build Contexts and Dockerfile Inventory

### 10.1 Repository Structure for Docker Artifacts

The recommended repository layout for all Docker-related files:

```
ShoppingCompanion/
  frontend/
    Dockerfile
    .dockerignore
    package.json
    src/
  backend/
    Dockerfile
    .dockerignore
    requirements.txt
    app/
  search-worker/
    Dockerfile
    .dockerignore
    requirements.txt
    app/
  websocket/
    Dockerfile
    .dockerignore
    requirements.txt
    app/
  config/
    nginx/
      default.conf
      upstream.conf
    postgres/
      init/
        01-create-roles.sql
        02-create-databases.sql
    shared/
      feature-flags.yml
  docker-compose.yml
  docker-compose.dev.yml
  docker-compose.override.yml.example
  .env.example
  .env.defaults
  .env.production
  .env.development
```

### 10.2 .dockerignore Specifications

Each service directory requires a `.dockerignore` file to minimize build context size and prevent accidental inclusion of secrets or development artifacts.

**frontend/.dockerignore must exclude:**

- `node_modules/` (hundreds of MB; reinstalled inside the builder stage)
- `.git/`
- `dist/` and `build/` (generated by local development builds)
- `*.env` and `.env*` (environment files with local secrets)
- `coverage/` and test output directories
- Editor configuration files (`.vscode/`, `.idea/`)
- `Dockerfile` and `docker-compose*.yml` (no reason to include in the build context)

**Python service .dockerignore files must exclude:**

- `__pycache__/` and `*.pyc` files
- `.pytest_cache/`, `htmlcov/`, `.coverage`
- `venv/`, `.venv/`, `.env/` (local virtual environment directories)
- `*.env` and `.env*`
- `.git/`
- `tests/` (for production builds; include in test-stage builds)
- `*.md` documentation files
- Editor configuration files

Keeping build contexts small directly reduces build time and network transfer time when using remote builders or Docker Build Cloud.

---

## 11. CI/CD Integration Considerations

### 11.1 Build Ordering and Parallelism

In CI, the four custom-built images (frontend, backend, search-worker, websocket) can be built in parallel since there are no inter-image build dependencies. The official images (postgres, redis) require no build step.

Build parallelism is expressed via Docker Bake using an HCL bake file that defines all four targets. The bake file enables BuildKit's parallel stage execution within each image and parallel image builds across targets.

### 11.2 Image Tagging Strategy

Each image is tagged with three identifiers on every successful CI build:

- **Commit SHA tag:** `registry/shopping-companion/backend:sha-a1b2c3d` — immutable, points to a specific build forever
- **Branch tag:** `registry/shopping-companion/backend:main` — mutable, always points to the latest build on that branch
- **Semantic version tag:** `registry/shopping-companion/backend:1.4.2` — applied only when a release tag is pushed; immutable after creation

Deployments reference commit SHA tags for reproducibility. The `latest` tag is never used in production deployments.

### 11.3 Cache Strategy for CI

Remote BuildKit cache using a registry cache backend is the recommended approach. Each service's build pushes cache manifests to the registry alongside the image. Subsequent CI runs pull the cache before building, achieving high layer cache hit rates even across ephemeral CI runners.

The cache key strategy separates dependency installation layers from application source layers so that a source-only change does not invalidate the `pip install` or `npm ci` cache layer.

### 11.4 Vulnerability Scanning

Docker Scout or an equivalent scanner (Trivy, Grype) runs against each built image as a mandatory CI gate before pushing to the production registry. The scan blocks promotion if critical or high CVEs are found in the OS or application dependency layers. The scan results are stored as CI artifacts for audit trail purposes.

Image signing with cosign occurs after the vulnerability gate passes, creating a verifiable attestation that the image was scanned and passed before reaching the registry.

---

## 12. Known Constraints and Future Considerations

**search-worker image size:** The AI model dependency stack (PyTorch or similar) produces a large final image regardless of multi-stage optimization. A distroless base is not practical here due to the dynamic nature of ML framework native extensions. The image size should be accepted as a constraint and managed through efficient registry caching and pull-through mirrors closer to the deployment environment.

**WebSocket scaling:** The current design runs a single websocket container. If horizontal scaling is required, a sticky session strategy at the nginx load balancer level is needed, or the websocket service must be refactored to a fully stateless design using Redis as the sole connection state store. This is a planned Phase 2 architectural decision.

**Database migrations:** The migration execution strategy (init container vs entrypoint guard vs manual operator step) must be finalized before production deployment. The init container pattern (a short-lived container that runs Alembic and exits before the backend starts) is the recommended approach as it separates migration concerns from the application server lifecycle and supports `depends_on` ordering cleanly.

**GPU acceleration for search-worker:** If the production AI search workload requires GPU acceleration, the search-worker image must be based on an NVIDIA CUDA-enabled base image, the Docker daemon must be configured with the NVIDIA Container Toolkit, and the Compose service definition must include a `deploy.resources.reservations.devices` block specifying the GPU device. This variant should be maintained as a separate `Dockerfile.gpu` to avoid forcing all deployments to pull the much larger CUDA base image.

**Secret rotation:** The current design passes secrets via environment variables from `.env` files. For mature production deployments, this should evolve to a Vault, AWS Secrets Manager, or equivalent integration where secrets are injected at container startup rather than stored in files on the host.

---

*This document represents the complete Docker deployment architecture for the Shopping Companion application. Implementation teams should treat this as the authoritative reference for containerization decisions. Deviations from this design should be documented as architectural decision records (ADRs) with rationale.*
