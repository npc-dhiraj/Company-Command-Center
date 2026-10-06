# Company Command Center

Company Command Center is a scalable multi-tenant SaaS platform designed to connect a company's existing applications and transform disconnected operational data into a unified intelligence system.

## Project Status
- **Current Scope**: Phase 3 (Connector Framework & Secure Credential Storage)
- **Tech Stack**: Python 3.12, FastAPI, SQLAlchemy 2.x (asyncpg), PostgreSQL 16, Alembic, Docker Compose, Argon2id, PyJWT, Fernet (cryptography), pytest, ruff, mypy

## Local Setup & Development

### 1. Environment Configuration
Copy the `.env.example` template to create your local `.env` file:
```bash
cp .env.example .env
```
Ensure `JWT_SECRET_KEY` is set to a secret at least 32 characters long.

Generate the required `ENCRYPTION_KEY` (Fernet key for credential encryption):
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Set the generated key as `ENCRYPTION_KEY` in your `.env` file. The application will **refuse to start** without a valid key.

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
- **Liveness Check**: [http://localhost:8000/health](http://localhost:8000/health) -> `{"status": "ok"}`
- **Readiness Check**: [http://localhost:8000/health/ready](http://localhost:8000/health/ready) -> `{"status": "ok", "database": "ok"}`
- **Interactive OpenAPI Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Authentication Endpoints

| Endpoint | Method | Role / Access | Description |
| :--- | :--- | :--- | :--- |
| `/auth/register` | `POST` | Public | Register a new tenant organization and initial owner user |
| `/auth/login` | `POST` | Public | Authenticate via tenant slug, email, and password |
| `/auth/refresh` | `POST` | Public | Refresh expired access token using rotating refresh token |
| `/auth/logout` | `POST` | Public | Revoke a refresh token |
| `/auth/me` | `GET` | Authenticated | Get current authenticated user profile and tenant details |
| `/users` | `POST` | Owner or Admin | Create a new user within caller's tenant (admins cannot create owners) |
| `/users` | `GET` | Authenticated | List all users belonging to caller's tenant only |

### Curl Walkthrough: Register -> Current User Profile

```bash
# 1. Register a new tenant and owner user
REGISTER_RESPONSE=$(curl -s -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_name": "Acme Corp",
    "tenant_slug": "acme-corp",
    "email": "owner@acme.com",
    "full_name": "Acme Owner",
    "password": "SuperSecretPassword123!"
  }')

echo "Register Response:"
echo "$REGISTER_RESPONSE"

# Extract access token
ACCESS_TOKEN=$(echo "$REGISTER_RESPONSE" | grep -o '"access_token":"[^"]*' | grep -o '[^"]*$')

# 2. Get current user info using access token
curl -s -X GET http://localhost:8000/auth/me \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

---

## Connector Framework

The connector framework provides a generic SDK for integrating external services. In Phase 3, only the framework exists — no real integrations are implemented yet.

| Endpoint | Method | Role / Access | Description |
| :--- | :--- | :--- | :--- |
| `/connectors` | `GET` | Authenticated | List registered connector types with metadata and credential fields |
| `/connections` | `POST` | Owner or Admin | Create a new connection (validates and tests credentials) |
| `/connections` | `GET` | Authenticated | List connections for caller's tenant |
| `/connections/{id}` | `GET` | Authenticated | Get a single connection (own tenant only) |
| `/connections/{id}/test` | `POST` | Owner or Admin | Re-test a connection and update status |
| `/connections/{id}` | `DELETE` | Owner or Admin | Hard-delete a connection and stored credentials |

Credentials are encrypted at rest using Fernet and are **never** returned by any endpoint. See `docs/connectors.md` for the full connector SDK documentation.

---

## 5. Running Tests & Quality Checks
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
