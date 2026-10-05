# Company Command Center - Phase 0 Documentation

## 1. Overview
**Phase 0** establishes the technical foundation, project structure, containerized development environment, quality tooling, and architectural baseline for the **Company Command Center** platform.

The goal of Company Command Center is to build a scalable multi-tenant SaaS platform that connects a company's existing applications and turns disconnected data into a unified operational intelligence system.

---

## 2. Technical Stack & Pinned Dependencies

| Component | Choice | Pinned Version | Rationale / Usage |
|---|---|---|---|
| **Language** | Python | `3.12` | Modern type hints, high performance runtime |
| **Framework** | FastAPI | `0.115.0` | Asynchronous REST framework with OpenAPI generation |
| **ASGI Server** | Uvicorn | `0.31.0` | High-performance ASGI server |
| **Configuration** | Pydantic Settings | `2.5.2` | Type-safe environment variable parsing |
| **Database** | PostgreSQL | `16-alpine` | Relational storage engine with multi-tenancy support |
| **DB Driver** | Psycopg 3 | `3.2.3` | Modern PostgreSQL adapter for Python |
| **Containerization** | Docker / Compose | Compose v2 | Reproducible multi-container dev environment |
| **Test Runner** | Pytest / HTTPX | `8.3.3` / `0.27.2` | Automated testing & FastAPI TestClient |
| **Linter / Formatter** | Ruff | `0.6.9` | High-speed Python linter & code style enforcer |
| **Type Checker** | Mypy | `1.11.2` | Static type analysis with strict checks enabled |
| **VCS** | Git | 2.55+ | Source control management |

---

## 3. Directory Layout

```
Company Command Center/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   └── config.py          # Centralized configuration (pydantic-settings)
│   │   ├── connectors/            # Source app integration package (placeholder)
│   │   │   └── __init__.py
│   │   ├── ingestion/             # Data ingestion pipeline package (placeholder)
│   │   │   └── __init__.py
│   │   ├── normalization/         # Data normalization package (placeholder)
│   │   │   └── __init__.py
│   │   ├── storage/               # Data persistence package (placeholder)
│   │   │   └── __init__.py
│   │   ├── routes/                # API route handlers
│   │   │   ├── __init__.py
│   │   │   └── health.py          # GET /health endpoint
│   │   ├── services/              # Domain logic services (placeholder)
│   │   │   └── __init__.py
│   │   └── main.py                # FastAPI app initialization
│   ├── tests/
│   │   ├── __init__.py
│   │   └── test_health.py         # Pytest test suite for health endpoint
│   ├── Dockerfile                 # Multi-stage image with non-root appuser
│   ├── pyproject.toml             # Config for pytest, ruff, mypy
│   ├── requirements.txt           # Production dependencies
│   └── requirements-dev.txt       # Development & testing dependencies
├── docker/
│   └── .gitkeep                   # Reserved for future infrastructure files
├── docs/
│   └── decisions.md               # Architecture decision record (Multi-tenancy)
├── .dockerignore                  # Docker build context exclusion rules
├── .env                           # Local secrets & env overrides (ignored by git)
├── .env.example                   # Template environment configuration file
├── .gitignore                     # Git exclusion rules
├── docker-compose.yml             # Orchestration for postgres & backend services
├── phase0.md                      # Phase 0 documentation
└── README.md                      # Project setup & developer guide
```

---

## 4. Key Components & Implementation Details

### A. Environment Configuration (`backend/app/core/config.py`)
- Env vars are read exclusively in `app/core/config.py` using `pydantic-settings`.
- `DATABASE_URL` is dynamically constructed from `POSTGRES_*` variables (`postgresql://user:pass@host:port/dbname`).
- Fallback default values prevent initialization crashes during static type analysis (`mypy`).

### B. Health Endpoint (`backend/app/routes/health.py`)
- Endpoint: `GET /health`
- Response: `{"status": "ok"}`
- Scope: Liveness check only. Performs no database calls or external dependencies.

### C. Container Security & Orchestration (`docker-compose.yml` & `backend/Dockerfile`)
- **PostgreSQL Service**: Uses `postgres:16-alpine`. Port `5432` is strictly bound to `127.0.0.1`. Includes `pg_isready` health check.
- **Backend Service**: Built from `backend/Dockerfile`. Uses a non-root system user (`appuser:appgroup`). Depends on Postgres health check. Environment variables enforce failure via `${VAR:?error}` syntax if missing.

### D. Architectural Decision (`docs/decisions.md`)
- **Multi-Tenancy Strategy**: Shared database, shared schema with logical tenant isolation.
- **Enforcement**: Mandatory, indexed `tenant_id` column on all application tables. All queries and ORM operations strictly scope requests by `tenant_id`.

---

## 5. Quality Assurance & Verification Commands

All checks can be run locally or within the Docker backend container:

1. **Unit Tests**:
   ```bash
   pytest
   ```
2. **Linting & Code Style**:
   ```bash
   ruff check .
   ```
3. **Static Type Checking**:
   ```bash
   mypy app tests
   ```
4. **Git Ignore Verification**:
   ```bash
   git check-ignore -v .env
   ```

---

## 6. Summary Status

- **Phase 0 Status**: Completed & Committed to Git (`root-commit cccf8ce`).
- **Next Phase**: Phase 1 (Data Model, Database Migration & Storage Layer Setup).
