# Company Command Center

Company Command Center is a scalable multi-tenant SaaS platform designed to connect a company's existing applications and transform disconnected operational data into a unified intelligence system.

## Project Status
- **Current Scope**: Phase 0 (Foundation & Development Environment Setup)
- **Tech Stack**: Python 3.12, FastAPI, PostgreSQL 16, Docker & Docker Compose, pytest, ruff, mypy

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

### 3. Service Access & Endpoints
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)
- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

### 4. Running Tests & Quality Checks
Run pytest suite:
```bash
docker compose exec backend pytest
```

Run code linter and type checker:
```bash
docker compose exec backend ruff check .
docker compose exec backend mypy app tests
```
