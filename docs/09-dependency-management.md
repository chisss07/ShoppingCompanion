# Dependency Management Strategy: AI-Powered Shopping Companion

**Document Version:** 1.0
**Date:** March 15, 2026
**Last Updated:** March 15, 2026
**Status:** Active

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Dependency Philosophy](#dependency-philosophy)
3. [Frontend Dependencies](#frontend-dependencies)
4. [Backend Dependencies](#backend-dependencies)
5. [Version Pinning Strategy](#version-pinning-strategy)
6. [Dependency Security](#dependency-security)
7. [Lock File Management](#lock-file-management)
8. [Update Cadence](#update-cadence)
9. [License Compliance](#license-compliance)
10. [Dependency Monitoring](#dependency-monitoring)
11. [Incident Response](#incident-response)
12. [Documentation and Tooling](#documentation-and-tooling)

---

## Executive Summary

This document establishes the dependency management framework for the Shopping Companion application, a full-stack AI-powered system integrating React 18+, Python 3.12+ FastAPI, PostgreSQL 16, Redis 7, and the Anthropic Claude API.

**Key Principles:**
- **Security First:** Zero critical vulnerabilities tolerance policy
- **Stability:** Conservative version selection with thorough testing
- **Performance:** Minimal bundle sizes and optimized dependency resolution
- **Compliance:** 100% license compatibility verification
- **Reproducibility:** Strict lock file enforcement across all environments

**Target Metrics:**
- Security patch deployment: < 7 days for critical vulnerabilities
- Regular update cycle: Monthly for minor/patch versions
- Bundle size optimization: < 500 KB gzipped (frontend main bundle)
- Build time: < 2 minutes for clean builds
- Zero critical CVE violations in production

---

## Dependency Philosophy

### Core Principles

1. **Minimal Dependencies:** Include only what is necessary; avoid transitive bloat
2. **Stability Over Novelty:** Prefer established, well-maintained packages
3. **LTS and Long-Term Support:** Prioritize packages with extended support windows
4. **Community Consensus:** Select packages with strong community adoption
5. **Active Maintenance:** Verify packages receive regular updates and security patches

### Dependency Selection Criteria

Each new dependency must satisfy:
- Active maintenance (commits within last 90 days)
- Minimum 100 GitHub stars (maturity indicator)
- Clear security vulnerability disclosure process
- Compatible license (MIT, Apache 2.0, BSD preferred)
- Low tree depth (avoid deep transitive dependencies)
- Peer review and team consensus before integration

---

## Frontend Dependencies

### Technology Stack
- **Runtime:** Node.js 20 LTS (3 year support window through April 2027)
- **Package Manager:** npm 10.x with package-lock.json
- **Build Tool:** Vite 5.x
- **Runtime Framework:** React 18.x
- **Language:** TypeScript 5.x

### Core Dependencies

#### React Ecosystem
```
react: ^18.3.0
react-dom: ^18.3.0
react-router-dom: ^6.28.0
```

**Rationale:**
- React 18.3.0: Latest stable with concurrent rendering features
- react-router-dom 6.28.0: Latest v6 with full TypeScript support and improved data APIs
- Maintain within ^18.x to leverage Suspense, useTransition, and useDeferredValue

**Migration Path:** React 19.x (when released) will be evaluated after 6-month stabilization window

#### TypeScript
```
typescript: ^5.6.0
```

**Rationale:**
- TypeScript 5.6 includes improved type inference and better error messages
- Locked to ^5.x for 3-5 year support window
- Supports latest ECMAScript features used by Vite/React

#### Build Tools
```
vite: ^5.4.0
@vitejs/plugin-react: ^4.3.0
```

**Rationale:**
- Vite 5.4.0: Stable production build tool with excellent HMR
- Plugin maintains parity with Vite versioning

### UI Component Library: Shadcn/ui

```
@radix-ui/react-alert-dialog: ^1.1.2
@radix-ui/react-dropdown-menu: ^2.1.2
@radix-ui/react-navigation-menu: ^1.2.1
@radix-ui/react-popover: ^1.1.2
@radix-ui/react-select: ^2.1.2
@radix-ui/react-slot: ^2.1.0
class-variance-authority: ^0.7.0
clsx: ^2.1.1
lucide-react: ^0.468.0
tailwindcss: ^3.4.14
```

**Rationale:**
- Shadcn/ui: Copy-paste component library (composable Radix primitives)
- Radix UI: Unstyled, accessible component primitives
- Tailwind CSS: Utility-first CSS framework for rapid UI development
- Lucide: Consistent icon library (468+ icons, actively maintained)
- Zero npm install overhead; components are source code

**Advantages Over Alternatives:**
- Material-UI: Heavy bundle, opinionated styling
- Chakra UI: Good but requires additional dependencies
- Bootstrap: Outdated design patterns, jQuery legacy
- shadcn/ui: Lightweight, customizable, modern design patterns

### State Management: Zustand

```
zustand: ^4.5.5
```

**Rationale:**
- Lightweight (2 KB gzipped) vs Redux Toolkit (5 KB)
- Minimal boilerplate with intuitive API
- Excellent DevTools support (Zustand DevTools)
- No external context dependencies
- Perfect for mid-complexity state (shopping lists, filters, user preferences)

**Use Cases in Shopping Companion:**
- Shopping cart state
- Applied filters and sorting
- User authentication state
- WebSocket connection state
- Notification queue

**Alternative Considered:** Redux Toolkit (eliminated due to verbosity for our use case)

### HTTP Client: Axios

```
axios: ^1.7.7
```

**Rationale:**
- Battle-tested (20K+ stars)
- Built-in request/response interceptors (critical for auth tokens)
- Timeout handling and request cancellation
- Backward compatibility guarantee
- Better error handling than native fetch

**Use Cases:**
- API requests to FastAPI backend
- Retry logic for network failures
- Request timeout handling (15 seconds default)

### WebSocket: Socket.IO Client

```
socket.io-client: ^4.8.1
```

**Rationale:**
- Real-time shopping list synchronization across devices
- Automatic reconnection with exponential backoff
- Room-based messaging for multi-user collaboration
- Browser compatibility across all modern browsers
- Fallback to polling if WebSocket unavailable

### Data Visualization: Recharts

```
recharts: ^2.14.2
```

**Rationale:**
- React-native charting library (10K+ stars)
- Responsive design built-in
- Excellent TypeScript support
- Small bundle impact (23 KB gzipped)
- Perfect for price history visualization

**Use Cases:**
- Price trend charts over time
- Historical shopping analytics
- Budget tracking visualizations

### Testing Stack

```
vitest: ^1.6.0
@testing-library/react: ^14.2.1
@testing-library/jest-dom: ^6.4.6
@testing-library/user-event: ^14.5.2
jsdom: ^24.1.1
```

**Rationale:**
- Vitest: Fast unit testing (ESM native, Vite integration)
- React Testing Library: Testing best practices (user-centric)
- Jest-dom: Semantic assertions for DOM testing
- JSDOM: Lightweight DOM simulation for tests

**Testing Philosophy:**
- Unit tests: > 80% coverage for business logic
- Integration tests: Critical user workflows
- E2E tests: Separate tool (Playwright/Cypress)
- Avoid testing implementation details

### Development Dependencies

```
@typescript-eslint/eslint-plugin: ^7.18.0
@typescript-eslint/parser: ^7.18.0
eslint: ^9.0.0
prettier: ^3.3.3
postcss: ^8.4.40
autoprefixer: ^10.4.20
```

**Rationale:**
- ESLint + Prettier: Code quality and consistent formatting
- PostCSS: CSS processing for Tailwind and vendor prefixes
- All tools configured via config files (no hardcoded rules)

### Frontend Dependency Summary Table

| Category | Package | Version | Rationale |
|----------|---------|---------|-----------|
| Core | react | ^18.3.0 | Latest stable, concurrent features |
| Core | react-dom | ^18.3.0 | Paired with React |
| Core | react-router-dom | ^6.28.0 | Full TypeScript, modern APIs |
| Language | typescript | ^5.6.0 | Latest stable, 5.x support window |
| Build | vite | ^5.4.0 | Fast, reliable build tool |
| Build | @vitejs/plugin-react | ^4.3.0 | React plugin parity |
| UI | @radix-ui/* | ^1.x-^2.x | Accessible primitives |
| UI | tailwindcss | ^3.4.14 | Utility-first CSS |
| UI | lucide-react | ^0.468.0 | Icon library |
| Icons | class-variance-authority | ^0.7.0 | Variant composition |
| Icons | clsx | ^2.1.1 | Class name utilities |
| State | zustand | ^4.5.5 | Lightweight state management |
| HTTP | axios | ^1.7.7 | Request/response handling |
| WebSocket | socket.io-client | ^4.8.1 | Real-time communication |
| Charts | recharts | ^2.14.2 | React-native charting |
| Test | vitest | ^1.6.0 | Fast unit testing |
| Test | @testing-library/react | ^14.2.1 | React testing best practices |
| Test | jsdom | ^24.1.1 | DOM simulation |

---

## Backend Dependencies

### Technology Stack
- **Runtime:** Python 3.12.x (October 2025 - October 2028 support)
- **Package Manager:** Poetry or pip-tools with requirements.txt/poetry.lock
- **Web Framework:** FastAPI 0.111.x
- **Async Runtime:** Uvicorn 0.28.x

### Core Web Framework

```
fastapi==0.111.0
uvicorn[standard]==0.28.0
pydantic==2.8.2
pydantic-settings==2.4.0
python-multipart==0.0.6
```

**Rationale:**
- FastAPI 0.111.0: Latest stable, async-first, automatic OpenAPI docs
- Uvicorn 0.28.0: ASGI server with uvloop for performance
- Pydantic 2.8.2: Data validation with strict mode support
- python-multipart: Form data handling for file uploads

**Design Notes:**
- All route handlers must use async/await
- Pydantic v2 strict mode enabled for validation rigor
- Request timeouts set to 30 seconds (configurable per route)

### Database: PostgreSQL + SQLAlchemy

```
sqlalchemy==2.0.29
asyncpg==0.30.0
alembic==1.13.1
psycopg2-binary==2.9.12
```

**Rationale:**
- SQLAlchemy 2.0: Modern ORM with async support (critical for Shopping Companion)
- asyncpg: High-performance PostgreSQL driver for async operations
- Alembic 1.13.1: Database migration management (must use for every schema change)
- PostgreSQL 16: Advanced JSON support, improved query performance

**Database Connection Pool:**
- Min connections: 5
- Max connections: 20
- Recycling: 3600 seconds (prevent connection timeout)
- Echo SQL logs only in development

**Migration Policy:**
- All schema changes require Alembic migrations
- Migrations stored in `migrations/versions/`
- Version naming: `{timestamp}_{description}.py`
- Up/Down functions must be idempotent
- Test migrations before deployment

### Caching: Redis

```
redis==5.0.7
aioredis==2.0.1
```

**Rationale:**
- redis-py 5.0.7: Official Redis Python client
- aioredis: Async support for concurrent operations
- Redis 7.x: Minimal version requirement

**Use Cases:**
- Session token caching (TTL: 24 hours)
- Shopping list temporary state (TTL: 30 minutes)
- API rate limiting (Token bucket algorithm)
- WebSocket room state synchronization
- Claude API response caching (TTL: 6 hours)

**Key Expiration Policy:**
- Session tokens: 24 hours
- Temporary data: 30 minutes
- API cache: 6 hours
- Rate limit counters: 1 hour
- Manual cleanup jobs: Daily (nightly 2 AM UTC)

### AI Integration: Anthropic SDK

```
anthropic==0.32.0
```

**Rationale:**
- Official Anthropic Python SDK
- Full support for Claude 3 family models
- Streaming responses for real-time UI feedback
- Integrated retry logic with exponential backoff
- Latest safety and usage policies

**API Configuration:**
- Model: `claude-3-5-sonnet-20241022` (cost-optimized, high quality)
- Max tokens: 1024 (default, context-specific)
- Temperature: 0.7 (balanced creativity)
- Top-p: 1.0 (unrestricted)
- Timeout: 30 seconds

**Fallback Strategy:**
- Retry on network errors: 3 attempts with exponential backoff
- Graceful degradation to basic recommendations if API fails
- Cache Claude responses for identical shopping lists (6 hour TTL)

### Web Scraping Dependencies

```
httpx==0.27.0
beautifulsoup4==4.12.3
```

**Rationale:**
- httpx: Modern HTTP client with async support (timeout 10 seconds)
- BeautifulSoup4: HTML parsing and DOM navigation
- No Selenium/Playwright needed for basic scraping

**Scraping Policy:**
- Respect robots.txt
- 2-second delay between requests per domain
- User-Agent header: `ShoppingCompanion/1.0`
- Cache responses (6-hour TTL) to minimize requests
- Graceful handling of timeouts/failures

**Future:** Consider Playwright if JavaScript rendering needed

### WebSocket: Socket.IO Python

```
python-socketio==5.10.0
python-engineio==4.8.0
aiohttp==3.9.7
```

**Rationale:**
- python-socketio 5.10.0: Server-side WebSocket handling
- aiohttp: ASGI/async HTTP for Socket.IO
- Real-time multi-user shopping list synchronization

**Rooms Architecture:**
- Room per shopping list: `shopping_list:{uuid}`
- Broadcast updates to all connected clients
- Disconnect handling with graceful cleanup
- Message queuing for offline users (optional)

### Testing Stack

```
pytest==7.4.4
pytest-asyncio==0.23.3
httpx[http2]==0.27.0
pytest-cov==4.1.0
factory-boy==3.3.0
faker==22.6.0
```

**Rationale:**
- pytest: Python standard testing framework
- pytest-asyncio: Async test support
- httpx: TestClient for API testing
- pytest-cov: Coverage reporting
- factory-boy: Fixture factories for test data
- faker: Random data generation

**Testing Standards:**
- > 80% code coverage (branches and lines)
- All routes must have integration tests
- Database tests must use rollback transactions
- Async test timeout: 30 seconds
- Skip external API calls in CI (use mocking)

### Utility Dependencies

```
python-dotenv==1.0.1
loguru==0.7.2
```

**Rationale:**
- python-dotenv: Environment variable management (.env files)
- loguru: Enhanced logging with levels and formatting

**Logging Configuration:**
- Development: DEBUG level, console output
- Production: INFO level, JSON format, stdout
- Exclude sensitive data (API keys, tokens) from logs

### Development Dependencies

```
black==24.3.0
isort==5.13.2
ruff==0.4.8
mypy==1.10.0
```

**Rationale:**
- black: Code formatting (strict, no configuration)
- isort: Import sorting
- ruff: Fast linting (Rust-based)
- mypy: Static type checking

### Backend Dependency Summary Table

| Category | Package | Version | Rationale |
|----------|---------|---------|-----------|
| Framework | fastapi | ==0.111.0 | Latest stable, async-first |
| Framework | uvicorn[standard] | ==0.28.0 | ASGI server |
| Framework | pydantic | ==2.8.2 | Data validation |
| Database | sqlalchemy | ==2.0.29 | Async ORM |
| Database | asyncpg | ==0.30.0 | PostgreSQL driver |
| Database | alembic | ==1.13.1 | Migration management |
| Database | psycopg2-binary | ==2.9.12 | PostgreSQL adapter |
| Cache | redis | ==5.0.7 | Redis client |
| Cache | aioredis | ==2.0.1 | Async Redis |
| AI | anthropic | ==0.32.0 | Claude API SDK |
| Scraping | httpx | ==0.27.0 | HTTP client |
| Scraping | beautifulsoup4 | ==4.12.3 | HTML parsing |
| WebSocket | python-socketio | ==5.10.0 | WebSocket server |
| WebSocket | python-engineio | ==4.8.0 | Engine.IO protocol |
| WebSocket | aiohttp | ==3.9.7 | Async HTTP |
| Test | pytest | ==7.4.4 | Testing framework |
| Test | pytest-asyncio | ==0.23.3 | Async test support |
| Test | pytest-cov | ==4.1.0 | Coverage reporting |
| Test | factory-boy | ==3.3.0 | Test fixtures |
| Test | faker | ==22.6.0 | Random data |
| Util | python-dotenv | ==1.0.1 | Environment variables |
| Util | loguru | ==0.7.2 | Logging |
| Dev | black | ==24.3.0 | Code formatting |
| Dev | isort | ==5.13.2 | Import sorting |
| Dev | ruff | ==0.4.8 | Fast linting |
| Dev | mypy | ==1.10.0 | Type checking |

---

## Version Pinning Strategy

### Principle: "Lock Everything"

**Policy:** All direct and transitive dependencies must be pinned to exact versions in lock files across all environments (development, staging, production).

### Frontend Version Pinning

#### Lock File: `package-lock.json`

**Generation:**
```
npm ci --prefer-offline --no-audit
```

**Never use:**
- `npm install` (can modify package-lock.json)
- `npm update` (should be intentional, separate workflow)
- Caret ranges (^) for production packages

**Installation:**
- Production: `npm ci --production`
- Development: `npm ci`

**Policy:**
- Commit package-lock.json to version control
- No manual modifications to lock file
- Review lock file changes in PR diffs
- Major version updates require team approval

### Backend Version Pinning

#### Option A: `requirements.txt` with Exact Pins

```
fastapi==0.111.0
uvicorn[standard]==0.28.0
pydantic==2.8.2
sqlalchemy==2.0.29
asyncpg==0.30.0
alembic==1.13.1
redis==5.0.7
anthropic==0.32.0
...
```

**Generation:**
```
pip freeze > requirements.txt
```

**Installation:**
```
pip install -r requirements.txt
```

#### Option B: `poetry.lock` with Poetry

```
[tool.poetry]
python = "^3.12"
fastapi = "0.111.0"
uvicorn = {version = "0.28.0", extras = ["standard"]}
...

[tool.poetry.dev-dependencies]
pytest = "7.4.4"
black = "24.3.0"
...
```

**Recommended:** Poetry for superior dependency resolution

**Installation:**
```
poetry install --no-interaction
```

**Update Workflow:**
```
poetry update [package-name]  # Updates specific package
poetry lock                    # Regenerates lock file
```

### Version Range Strategy

#### Semantic Versioning: MAJOR.MINOR.PATCH

**Policy for Direct Dependencies:**

| Stability | Range | When to Use |
|-----------|-------|------------|
| Production | `==X.Y.Z` | Critical packages, security patches |
| Stable | `~X.Y.Z` (patch only) | Mature packages with good practices |
| Maintenance | `^X.Y.Z` (minor + patch) | Active projects, within same major |
| Development | `latest` | Tools and linters only |

**Rationale:**
- `==`: Exact pins prevent surprise breaking changes
- `~`: Allows patch updates only (bug fixes)
- `^`: Allows minor/patch (semver.org compliant projects only)
- `latest`: Never for production code

**Exception Handling:**
- Pre-release versions (1.0.0-alpha): Approved by tech lead only
- Unstable majors (0.x.x): Review needed, full test suite required

### Transitive Dependency Management

**Transitive Dependencies:** Packages pulled in by your direct dependencies

**Strategy:**
- Lock all transitives in lock files
- Don't manually pin transitives (let lock file manage)
- Audit transitive tree for vulnerabilities
- If transitive has CVE, update parent package
- Document overrides in `DEPENDENCY_OVERRIDES.md`

**Tools:**
- Frontend: `npm ls` (tree view)
- Backend: `pip show [package]` or `poetry show --tree`

---

## Dependency Security

### Security First Philosophy

**Core Principle:** Zero critical vulnerabilities in production. All security patches applied within 7 days of release.

### Vulnerability Scanning

#### Frontend: npm audit

**Frequency:** Automated daily, manual on-demand

**Command:**
```
npm audit --production
```

**Severity Levels:**
- **CRITICAL:** Fix within 24 hours, emergency deployment authorized
- **HIGH:** Fix within 7 days, included in next release
- **MODERATE:** Fix within 30 days, grouped with other updates
- **LOW:** Fix within 60 days, optional for minor releases

**Action Items:**
- Create security issue in repository
- Link to CVE/advisory
- Assign to security team
- Set deadline based on severity
- Document remediation approach

#### Backend: Safety & Snyk

**Safety (First Line):**
```
pip install safety
safety check --json > safety-report.json
```

**Snyk (Advanced, Recommended):**
```
npm install -g snyk
snyk test --severity-threshold=high
```

**Frequency:** Daily in CI/CD, weekly manual review

**Configuration:**
- Fail build on CRITICAL/HIGH
- Report MODERATE/LOW in dashboard
- Exclude known false positives (with justification)

### Automated Security Updates

#### Dependabot Configuration (GitHub)

**File:** `.github/dependabot.yml`

```yaml
version: 2
updates:
  # Frontend
  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "08:00"
    security-updates-enabled: true
    open-pull-requests-limit: 5
    reviewers: ["security-team"]
    labels: ["dependencies", "security"]

  # Backend
  - package-ecosystem: "pip"
    directory: "/backend"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "09:00"
    security-updates-enabled: true
    open-pull-requests-limit: 5
    reviewers: ["security-team"]
    labels: ["dependencies", "security"]
```

**Process:**
- Dependabot creates PR for updates
- Automated tests run (unit + integration)
- Security review before merge
- Auto-merge for patch versions (optional)
- Manual merge for minor/major

### License Compliance Audit

**Tool:** FOSSA or Snyk License Check

**Licenses Allowed:**
- MIT
- Apache 2.0
- BSD (2-Clause, 3-Clause)
- ISC
- MPL 2.0
- LGPL 3.0

**Licenses Not Allowed:**
- GPL (business model conflict)
- AGPL (derivative work requirement)
- Proprietary (commercial licensing required)

**Review Process:**
- Audit before adding any new dependency
- Document any exceptions
- Legal review for edge cases
- Annual compliance review

---

## Lock File Management

### Purpose of Lock Files

Lock files ensure reproducible builds:
- Same versions across dev/staging/production
- Same versions for all developers
- Auditable dependency tree
- Security vulnerability tracking

### Frontend: package-lock.json

**Location:** `/package-lock.json`

**Commit Policy:**
- ALWAYS commit to version control
- Review changes in pull requests
- Never manually edit (only via npm commands)

**Integrity Verification:**
```
npm ci --production
```

**When to Update:**
1. Adding new dependency: `npm install [package]`
2. Removing dependency: `npm uninstall [package]`
3. Updating dependency: `npm update [package]`
4. Scheduled security updates: Via Dependabot PR

**CI/CD Integration:**
```bash
# Use CI mode to prevent modifications
npm ci --prefer-offline
npm run build
npm run test
```

### Backend: poetry.lock or requirements.txt

#### Using Poetry (Recommended)

**Location:** `/backend/poetry.lock`

**Commit Policy:**
- ALWAYS commit to version control
- Never manually edit
- Update via `poetry update` command

**Update Workflow:**
```bash
# Add new dependency
poetry add fastapi

# Remove dependency
poetry remove fastapi

# Update specific dependency
poetry update fastapi

# Update all dependencies
poetry update
```

**Installation:**
```bash
poetry install --no-interaction
```

#### Using requirements.txt (Alternative)

**Location:** `/backend/requirements.txt`

**Update Workflow:**
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install from requirements
pip install -r requirements.txt

# Add new package
pip install new-package

# Freeze all versions
pip freeze > requirements.txt
```

**Lock File Validation:**
```bash
# Verify all packages match lock file
pip install -r requirements.txt --check
```

### Lock File Verification in CI/CD

**GitHub Actions Workflow:**

```yaml
- name: Verify Dependencies
  run: |
    # Frontend
    npm ci

    # Backend
    cd backend
    poetry install --no-interaction
    poetry show
```

---

## Update Cadence

### Quarterly Update Schedule

**Philosophy:** Regular, planned updates prevent security debt accumulation

### Monthly Security Updates

**Timing:** First Monday of each month

**Process:**
1. Run vulnerability scans (npm audit, safety check)
2. Create dedicated branch: `deps/security-updates-YYYY-MM`
3. Update all CRITICAL/HIGH vulnerabilities
4. Run full test suite
5. Create PR with title: `chore: Security patch updates`
6. Review and merge within 48 hours

**Approval:** Security team + 1 backend reviewer

### Quarterly Minor/Patch Updates

**Timing:**
- Q1: January (first Monday)
- Q2: April (first Monday)
- Q3: July (first Monday)
- Q4: October (first Monday)

**Process:**
1. Create branch: `deps/quarterly-updates-YYYY-Qx`
2. Update all minor and patch versions within allowed ranges
3. Frontend: `npm update` (respects caret/tilde ranges)
4. Backend: `poetry update` (respects version constraints)
5. Run full test suite (unit + integration + e2e)
6. Performance benchmarking
7. Create PR with changelog
8. Review by tech lead + 2 developers
9. Merge and deploy to staging for 1 week before production

**Testing Requirements:**
- Unit test coverage > 80%
- Integration test suite 100% passing
- E2E smoke tests on staging environment
- Performance regression testing (bundle size, load time)
- Manual testing of critical paths (shopping, recommendations)

### Major Version Updates

**Policy:** Evaluated annually, require extended testing

**Schedule:** Planned in Q1 planning meetings

**Decision Criteria:**
- Breaking API changes impact?
- Migration complexity?
- New features value?
- Community adoption rate?
- Timeline for adoption (typically 6-12 months after release)

**Process:**
1. Create feature branch: `deps/major-upgrade-PACKAGE-vX`
2. Research breaking changes (review migration guides)
3. Update package and resolve all type errors
4. Update tests for API changes
5. Full regression testing
6. Create RFC (Request for Comments) document
7. Team discussion and approval
8. Staged rollout (dev → staging → production)
9. Post-deployment monitoring (1 week)

**Examples:**
- React 18 → 19: Requires component updates, Suspense migration
- FastAPI 0.100 → 0.111: Usually backward compatible, minor adjustments
- TypeScript 4 → 5: Type system improvements, requires review

### Dependency Update Matrix

| Update Type | Frequency | Security | Testing | Approval |
|------------|-----------|----------|---------|----------|
| Security patches | Weekly | CRITICAL: 24h, HIGH: 7d | Full suite | Auto-merge (if tests pass) |
| Patch version | Monthly | Yes | Full suite | 1 reviewer |
| Minor version | Quarterly | Yes | Full suite | 1 reviewer |
| Major version | Annually | Yes | Extensive | Tech lead + 2 devs |
| Pre-release | Never | N/A | N/A | Not allowed |

---

## License Compliance

### License Audit Process

**Timing:** On every new dependency addition, annually for all dependencies

**Tools:**
- Frontend: `npm-check-licenses` or FOSSA
- Backend: `pip-licenses` or Snyk

**Frontend License Audit:**

```bash
# Install license checker
npm install -g npm-check-licenses

# Generate report
npm-check-licenses --onlyAllow "MIT,Apache-2.0,BSD-2-Clause,BSD-3-Clause"
```

**Backend License Audit:**

```bash
# Install license checker
pip install pip-licenses

# Generate report
pip-licenses --format=markdown --with-urls > LICENSES.md
```

### License Compatibility Matrix

| License Type | Allowed | Notes |
|-------------|---------|-------|
| MIT | Yes | No restrictions, most permissive |
| Apache 2.0 | Yes | Patent clause beneficial |
| BSD-2-Clause | Yes | Similar to MIT |
| BSD-3-Clause | Yes | Similar to MIT |
| ISC | Yes | FOSS-compatible |
| MPL-2.0 | Yes | File-level copyleft, safe |
| LGPL-3.0 | Caution | Requires source disclosure for modifications |
| GPL-2.0 | No | Strong copyleft, incompatible with proprietary code |
| GPL-3.0 | No | Strong copyleft, incompatible |
| AGPL-3.0 | No | Network copyleft, hostile for SaaS |
| Proprietary | Case-by-case | Requires legal review |

### Dependency License Inventory

**Location:** `LICENSES_INVENTORY.md`

**Template:**

```markdown
# Dependency License Inventory
Last Updated: [DATE]

## Frontend Dependencies

| Package | Version | License | Notes |
|---------|---------|---------|-------|
| react | 18.3.0 | MIT | Core framework |
| typescript | 5.6.0 | Apache-2.0 | Language runtime |
| vite | 5.4.0 | MIT | Build tool |
| ...

## Backend Dependencies

| Package | Version | License | Notes |
|---------|---------|---------|-------|
| fastapi | 0.111.0 | MIT | Web framework |
| sqlalchemy | 2.0.29 | MIT | ORM |
| anthropic | 0.32.0 | MIT | AI SDK |
| ...

## Exceptions
None currently

## Review Status
- Last Reviewed: [DATE]
- Next Review: [DATE + 1 YEAR]
- Reviewed By: [NAME]
```

---

## Dependency Monitoring

### Continuous Monitoring Strategy

**Goal:** Proactive detection of security issues, deprecations, and compatibility problems

### Automated Scanning

#### CI/CD Pipeline Checks

**Trigger:** Every commit to main/develop branches

**Frontend Checks:**
```yaml
- npm ci
- npm audit --production  # Fail on CRITICAL/HIGH
- npm run lint           # ESLint for code quality
- npm run type-check     # TypeScript compilation
- npm run test           # Unit tests
- npm run build          # Production build
```

**Backend Checks:**
```yaml
- poetry install
- safety check           # Fail on CRITICAL/HIGH
- mypy .               # Type checking
- ruff check           # Linting
- black --check        # Format verification
- pytest               # Unit tests
- pytest --cov         # Coverage > 80%
```

### Manual Monitoring

**Weekly:**
- Check GitHub security alerts
- Review Snyk dashboard
- Monitor package update notifications

**Monthly:**
- Full dependency tree analysis
- CVE database manual check
- Community forums for deprecation announcements

**Quarterly:**
- License compliance audit
- Bundle size analysis
- Performance regression check

### Dependency Health Metrics

**Track:**
1. **Security Score:** CVEs present / total dependencies
2. **Update Lag:** Days since last update available
3. **Activity Level:** Commits per month (maintainer engagement)
4. **Community Health:** GitHub stars, forks, issues
5. **Test Coverage:** Lines/branches covered in dependency tests
6. **Bundle Impact:** Minified + gzipped size per dependency

**Targets:**
- Security Score: 0 critical vulnerabilities
- Update Lag: < 30 days for major updates
- Activity Level: > 2 commits/month
- Bundle Size: Keep main bundle < 500 KB gzipped
- Test Coverage: > 80% in dependencies we control

### Deprecation Tracking

**Process:**
1. Monitor release notes for deprecation warnings
2. Document deprecated APIs in codebase
3. Create migration tickets (quarterly)
4. Update code before versions removed (usually 2-3 major versions)
5. Validate removal in tests

**Example:**
- React.PropTypes deprecated in 15.5, removed in 16.0
- Action: Remove PropTypes by React 18 usage

---

## Incident Response

### Security Vulnerability Response Plan

**Severity Definitions:**

| Severity | CVSS Score | Fix Deadline | Action |
|----------|-----------|--------------|--------|
| CRITICAL | 9.0-10.0 | 24 hours | Emergency patch release |
| HIGH | 7.0-8.9 | 7 days | Next scheduled deployment |
| MEDIUM | 4.0-6.9 | 30 days | Next quarterly update |
| LOW | 0.1-3.9 | 60 days | Grouped with feature releases |

### Response Workflow

**Step 1: Detection**
- CVE published → Snyk alert → Slack notification
- GitHub dependabot creates security PR

**Step 2: Assessment**
- Read CVE details and affected versions
- Check if we're vulnerable (version check)
- Assess impact (user data risk, availability risk)
- Determine if affected code path is used

**Step 3: Remediation**
- Update package to patched version
- Run full test suite
- Verify fix in changelog
- Create security patch release if needed

**Step 4: Testing**
- Unit tests: 100% passing
- Integration tests: 100% passing
- Staging deployment: Smoke tests passing
- Performance: No regression

**Step 5: Deployment**
- Production deployment
- Monitor error rates (15 minutes)
- Rollback if issues detected

**Step 6: Documentation**
- Post-incident review
- Update CHANGELOG.md with security note
- Communicate fix to customers if necessary

### Communication Template

**Internal Alert:**
```
SECURITY ALERT: [PACKAGE] CVE-XXXX-XXXXX

Severity: [CRITICAL/HIGH/MEDIUM/LOW]
Affected Version: [Current version]
Fixed Version: [Updated version]
Impact: [Description of vulnerability]
Fix ETA: [Time until deployed]
Action Required: [For other team members]
```

**Customer Communication (if necessary):**
```
We've identified and patched a security issue in [COMPONENT].
Patched Version: [Version number]
Affected Versions: [List]
Timeline: Deployed on [DATE]
Your Risk: [Assessment]
Action Needed: [If any]
```

---

## Documentation and Tooling

### Repository Structure

```
shopping-companion/
├── package.json                    # Frontend dependencies
├── package-lock.json               # Frontend lock file
├── backend/
│   ├── pyproject.toml             # Poetry configuration
│   ├── poetry.lock                # Backend lock file
│   └── requirements.txt            # Alternative: pip requirements
├── DEPENDENCY_MANAGEMENT_STRATEGY.md  # This document
├── LICENSES_INVENTORY.md           # License audit report
├── DEPENDENCY_OVERRIDES.md         # Documented overrides
└── .github/
    ├── dependabot.yml             # Automated updates
    └── workflows/
        ├── security-scan.yml      # Vulnerability checks
        └── dependency-audit.yml   # License audit
```

### Configuration Files

#### Frontend: package.json

**Key Sections:**
```json
{
  "name": "shopping-companion",
  "version": "1.0.0",
  "engines": {
    "node": ">=20.0.0",
    "npm": ">=10.0.0"
  },
  "dependencies": {
    "react": "^18.3.0",
    "typescript": "^5.6.0"
  },
  "devDependencies": {
    "vitest": "^1.6.0",
    "eslint": "^9.0.0"
  }
}
```

**Scripts:**
```json
{
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext .ts,.tsx",
    "type-check": "tsc --noEmit",
    "format": "prettier --write .",
    "test": "vitest",
    "test:cov": "vitest --coverage",
    "audit": "npm audit --production"
  }
}
```

#### Backend: pyproject.toml (Poetry)

```toml
[tool.poetry]
name = "shopping-companion-api"
version = "1.0.0"
description = "AI-powered shopping assistant API"
authors = ["Your Team"]

[tool.poetry.dependencies]
python = "^3.12"
fastapi = "0.111.0"
uvicorn = {version = "0.28.0", extras = ["standard"]}
pydantic = "2.8.2"

[tool.poetry.dev-dependencies]
pytest = "7.4.4"
pytest-asyncio = "0.23.3"
black = "24.3.0"
mypy = "1.10.0"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
```

#### Backend: setup.cfg (Configuration)

```ini
[metadata]
name = shopping-companion-api

[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
addopts = --cov --cov-branch --cov-report=term-missing

[mypy]
python_version = 3.12
strict = True
warn_return_any = True
disallow_untyped_defs = True

[tool:black]
line-length = 100
target-version = ['py312']

[tool:ruff]
line-length = 100
target-version = "py312"
```

### Dependency Documentation Template

**For each major dependency, maintain:**

**Location:** `docs/dependencies/[PACKAGE].md`

```markdown
# Dependency: [Package Name]

## Overview
- **Version:** X.Y.Z
- **License:** MIT
- **Latest Release:** [Date]
- **Last Updated:** [Date]
- **Update Frequency:** Quarterly

## Purpose
[What problem does this dependency solve?]

## Why This Package
[Comparison with alternatives and rationale for selection]

## Usage
[How we use it in the application]

## Version History
- 1.0.0 (Current): [Changes]
- 0.9.0: [Changes]

## Known Issues
[Any limitations or workarounds]

## Deprecation Risk
[Is this package being deprecated? When?]

## Security Notes
[Any security-related configurations or known vulnerabilities]

## Migration Plan
[If replacing this package, how would we do it?]
```

### Team Documentation

**File:** `DEPENDENCY_MANAGEMENT_RUNBOOK.md`

```markdown
# Dependency Management Runbook

## Adding a New Dependency

### Frontend
1. Research package on npm (stars, maintenance, security)
2. Check license compatibility
3. `npm install [package]`
4. Review changes to package-lock.json
5. Add to LICENSES_INVENTORY.md
6. Create PR with title: `feat: Add [package] for [purpose]`

### Backend
1. Research package on PyPI
2. Check license compatibility
3. `poetry add [package]`
4. Review changes to poetry.lock
5. Add to LICENSES_INVENTORY.md
6. Create PR with title: `feat: Add [package] for [purpose]`

## Updating Dependencies

### Scheduled Monthly Updates
1. Create branch: `deps/updates-[YYYY-MM]`
2. Run vulnerability scan
3. Update packages (minor/patch only)
4. Run full test suite
5. Create PR for review
6. Merge to develop after approval

### Emergency Security Updates
1. Create branch: `deps/security-PACKAGE`
2. Update only the vulnerable package
3. Fast-track through review
4. Deploy to production immediately if tests pass

## Handling Dependency Conflicts

### Scenario: Two packages want different versions of lodash

**Solution:**
1. Analyze if version gap is critical
2. Try updating one of the dependents
3. Check npm/poetry for version resolution
4. Document override if necessary
5. Add to DEPENDENCY_OVERRIDES.md

## Responding to a CVE

1. Receive alert from Snyk/Dependabot
2. Assess severity using CVSS score
3. Follow incident response workflow
4. Deploy fix within deadline
5. Document in CHANGELOG.md

## Removing Unused Dependencies

1. Verify no code references the package
2. Remove from package.json or pyproject.toml
3. Run build and test suite
4. Commit with message: `chore: Remove unused [package]`
5. Update bundle size metrics

## Performance Optimization

1. Analyze bundle size: `npm run build --analyze`
2. Identify large dependencies
3. Look for alternatives or tree-shaking
4. Consider lazy loading (React.lazy)
5. Update build config for optimization
```

### Monitoring Dashboard

**Create a dependency health dashboard showing:**
- Number of vulnerabilities (by severity)
- Outdated packages (by days)
- License compliance status
- Bundle size trend
- Update lag metrics
- Last security audit date

**Tools:**
- Snyk Dashboard (free tier available)
- GitHub dependency graph (built-in)
- Custom dashboard (spreadsheet or tool)

---

## Appendices

### A. Emergency Contacts

**Security Team Lead:** [Name] - [Email]
**Tech Lead:** [Name] - [Email]
**DevOps Lead:** [Name] - [Email]

### B. Related Documents

- [CONTRIBUTING.md](CONTRIBUTING.md) - Contribution guidelines
- [SECURITY.md](SECURITY.md) - Security policy
- [CHANGELOG.md](CHANGELOG.md) - Release notes
- [BUILD.md](BUILD.md) - Build and deployment procedures

### C. External References

**Security Standards:**
- [OWASP Dependency Check](https://owasp.org/www-project-dependency-check/)
- [NIST Vulnerability Database](https://nvd.nist.gov/)
- [CWE Top 25](https://cwe.mitre.org/top25/)

**Standards:**
- [Semantic Versioning](https://semver.org/)
- [SBOM Standards](https://cyclonedx.org/)
- [Open Source License Guide](https://opensource.org/licenses/)

**Tools Documentation:**
- [npm Audit Documentation](https://docs.npmjs.com/cli/audit)
- [Poetry Documentation](https://python-poetry.org/docs/)
- [Snyk Documentation](https://docs.snyk.io/)
- [Dependabot Documentation](https://docs.github.com/en/code-security/dependabot)

### D. Version Pinning Examples

**Frontend package.json (Recommended Ranges):**
```json
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-router-dom": "^6.28.0",
    "axios": "^1.7.7",
    "zustand": "^4.5.5",
    "socket.io-client": "^4.8.1"
  },
  "devDependencies": {
    "typescript": "^5.6.0",
    "vite": "^5.4.0",
    "@vitejs/plugin-react": "^4.3.0",
    "vitest": "^1.6.0",
    "eslint": "^9.0.0",
    "prettier": "^3.3.3"
  }
}
```

**Backend pyproject.toml (Recommended Ranges):**
```toml
[tool.poetry.dependencies]
python = "^3.12"
fastapi = "0.111.0"
uvicorn = "0.28.0"
sqlalchemy = "2.0.29"
asyncpg = "0.30.0"
redis = "5.0.7"
anthropic = "0.32.0"
httpx = "0.27.0"
beautifulsoup4 = "4.12.3"

[tool.poetry.dev-dependencies]
pytest = "7.4.4"
pytest-asyncio = "0.23.3"
black = "24.3.0"
mypy = "1.10.0"
ruff = "0.4.8"
```

### E. Security Checklist

**Before Production Deployment:**
- [ ] All CRITICAL/HIGH vulnerabilities fixed
- [ ] Full test suite passing (unit, integration, e2e)
- [ ] No new dependencies added without approval
- [ ] License compliance audit passed
- [ ] Bundle size within targets (< 500 KB gzipped)
- [ ] Type checking passing (TypeScript, mypy)
- [ ] Linting passing (ESLint, Ruff)
- [ ] Code formatting compliant (Prettier, Black)
- [ ] Documentation updated
- [ ] Security review completed

---

## Document Control

**Document Version:** 1.0
**Last Updated:** March 15, 2026
**Next Review:** March 15, 2027
**Status:** Active
**Approval:** [Tech Lead Name]

### Change History

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-03-15 | Dependency Manager | Initial comprehensive strategy document |

---

**This document is living documentation. Update it as your team's practices, technologies, and policies evolve. Review and refresh annually.**
