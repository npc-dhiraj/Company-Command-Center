# Company Command Center

Company Command Center is a scalable multi-tenant SaaS platform designed to connect a company's existing applications and transform disconnected operational data into a unified intelligence system.

## Project Status
- **Current Scope**: Phase 1 (Database Foundation & Multi-Tenant Core)
- **Tech Stack**: Python 3.12, FastAPI, SQLAlchemy 2.x (asyncpg), PostgreSQL 16, Alembic, Docker Compose, pytest, ruff, mypy

## Local Setup & Development

### 1. Environment Configuration
Copy the `.env.example` template to create your local `.env` file:
```bash
cp .env.example .env
```

### 2. Start Services with Docker Compose
Build and start the PostgreSQL database and backend service:
```bash
docker compose up -d --build
```

### 3. Database Migrations
Migrations are run explicitly via Alembic:
```bash
# Apply migrations to latest version
docker compose exec backend alembic upgrade head

# Rollback one migration step
docker compose exec backend alembic downgrade -1
```

### 4. Service Access & Health Endpoints
- **Liveness Check**: [http://localhost:8000/health](http://localhost:8000/health) -> `{"status": "ok"}` (Pure liveness check, no DB calls)
- **Readiness Check**: [http://localhost:8000/health/ready](http://localhost:8000/health/ready) -> `{"status": "ok", "database": "ok"}` (Verifies database connectivity via `SELECT 1`)
- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

### 5. Running Tests & Quality Checks
Run non-database unit tests:
```bash
docker compose exec backend pytest -m "not db"
```

Run all tests (including database integration tests):
```bash
docker compose exec backend pytest
```

Run linter and type checker:
```bash
docker compose exec backend ruff check .
docker compose exec backend mypy app tests
```
