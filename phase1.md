# Company Command Center - Phase 1 Documentation

## 1. Overview
**Phase 1** builds the database foundation and multi-tenant core models for the **Company Command Center** platform. 

It establishes an asynchronous database layer powered by **SQLAlchemy 2.x** and **asyncpg**, sets up database migrations using **Alembic**, implements the core `Tenant` and `User` domain models with strict multi-tenant isolation rules, introduces a DB readiness health check (`GET /health/ready`), and adds integration tests with database fixtures.

---

## 2. Technical Stack & Pinned Dependencies

In addition to Phase 0 dependencies, Phase 1 introduces and pins the following runtime and development packages:

| Component | Choice | Pinned Version | Purpose |
|---|---|---|---|
| **ORM Framework** | SQLAlchemy | `2.0.35` | Async object-relational mapping & declarative models |
| **Async DB Driver** | asyncpg | `0.29.0` | High-performance PostgreSQL async driver |
| **Migrations Engine** | Alembic | `1.13.3` | Database schema migrations and revision control |
| **Async Loop Support** | greenlet | `3.1.1` | Required for SQLAlchemy async engine execution |
| **Async Test Runner** | pytest-asyncio | `0.24.0` | Async fixture support for pytest |

---

## 3. Directory Layout (Phase 1 Additions & Updates)

```
Company Command Center/
├── backend/
│   ├── alembic.ini                # Alembic configuration file
│   ├── migrations/
│   │   ├── env.py                 # Async Alembic environment runner
│   │   ├── script.py.mako         # Migration version template script
│   │   └── versions/
│   │       └── 2026_10_05_0000-0001_initial_tenants_and_users.py  # Initial schema migration
│   ├── app/
│   │   ├── core/
│   │   │   ├── config.py          # Updated with postgresql+asyncpg:// connection URL
│   │   │   └── database.py        # Async engine, session factory, get_session, lifespan disposal
│   │   ├── storage/
│   │   │   ├── base.py            # DeclarativeBase, constraint naming, UUID, Timestamp & TenantOwned mixins
│   │   │   └── models/
│   │   │       ├── __init__.py
│   │   │       ├── tenant.py      # Tenant ORM model
│   │   │       └── user.py        # User ORM model
│   │   ├── routes/
│   │   │   └── health.py          # Added GET /health/ready endpoint
│   │   └── main.py                # Updated to pass lifespan context manager
│   ├── tests/
│   │   ├── conftest.py            # Session-scoped test engine & session fixtures
│   │   ├── test_database.py       # DB integration tests (Schema, Tenant/User CRUD, unique constraints)
│   │   └── test_health.py         # Liveness and 503 readiness mock failure tests
│   ├── pyproject.toml             # Added asyncio_mode, db markers, and mypy overrides
│   ├── requirements.txt           # Pinned runtime dependencies
│   └── requirements-dev.txt       # Pinned dev dependencies
├── docs/
│   ├── database.md                # DB architecture conventions & migration operations guide
│   └── decisions.md               # ADR updated with Async SQLAlchemy, UUIDs, Explicit Migrations
├── phase1.md                      # Phase 1 documentation
└── README.md                      # Updated with migration commands and endpoint docs
```

---

## 4. Key Architectural Implementations

### A. Database Session Management (`backend/app/core/database.py`)
- **Async Engine**: Created via `create_async_engine(settings.DATABASE_URL)` using `postgresql+asyncpg://`.
- **Session Factory**: `async_sessionmaker` configured with `expire_on_commit=False` to prevent lazy loading issues after transaction commits.
- **FastAPI Dependency (`get_session`)**: Provides one `AsyncSession` per request with automatic cleanup (`rollback()` on exception, `close()` on exit).
- **Lifespan Cleanup**: Application lifespan disposes of the database engine (`await engine.dispose()`) on shutdown.

### B. Declarative Base & Reusable Mixins (`backend/app/storage/base.py`)
- **Constraint Naming Convention**: Standardized naming (`pk_%`, `fk_%`, `uq_%`, `ix_%`, `ck_%`) for deterministic Alembic migrations.
- **`UUIDPrimaryKeyMixin`**: Application-generated UUID v4 (`uuid4`) primary key `id`.
- **`TimestampMixin`**: Timezone-aware UTC timestamps (`created_at`, `updated_at`) with `server_default=func.now()`.
- **`TenantOwnedMixin`**: Reusable mixin providing a mandatory, non-null, indexed `tenant_id` foreign key referencing `tenants.id` with `ON DELETE CASCADE`.

### C. Multi-Tenant Data Models (`backend/app/storage/models/`)
1. **`Tenant` Model (`tenants` table)**:
   - `id`: UUID (PK)
   - `name`: String(255), non-null
   - `slug`: String(255), unique, indexed, non-null
   - `is_active`: Boolean, default `True`
   - `created_at`, `updated_at`: `TIMESTAMPTZ`
   - Relationship: `users` (cascade delete orphan)
2. **`User` Model (`users` table)**:
   - `id`: UUID (PK)
   - `tenant_id`: UUID (FK -> `tenants.id`, indexed) via `TenantOwnedMixin`
   - `email`: String(255), non-null
   - `full_name`: String(255), non-null
   - `is_active`: Boolean, default `True`
   - `created_at`, `updated_at`: `TIMESTAMPTZ`
   - Unique Constraint: `uq_users_tenant_id_email` on `(tenant_id, email)` — allows identical emails in different tenants while enforcing uniqueness within a tenant.

### D. Health & Readiness Endpoints (`backend/app/routes/health.py`)
- **`GET /health`**: Pure liveness check returning `{"status": "ok"}` with zero database calls.
- **`GET /health/ready`**: Readiness check executing `SELECT 1` through the database session.
  - Returns `200 {"status": "ok", "database": "ok"}` when the database responds.
  - Returns `503 {"status": "unavailable", "database": "error"}` if database connection fails, concealing raw stack traces and credentials.

---

## 5. Migration Strategy & Versioning

- **Explicit Execution**: Migrations are run manually using `docker compose exec backend alembic upgrade head`.
- **Initial Migration (`0001_initial`)**: Generates both `tenants` and `users` tables, indices, foreign keys, and unique constraints.

---

## 6. Verification & Quality Assurance

All static checks and non-database unit tests pass cleanly:

1. **Non-DB Unit Tests**:
   ```bash
   pytest -m "not db"
   # Output: 2 passed, 5 deselected in 0.48s
   ```
2. **Code Style & Linting**:
   ```bash
   ruff check .
   # Output: All checks passed!
   ```
3. **Static Type Checking**:
   ```bash
   mypy app tests
   # Output: Success: no issues found in 20 source files
   ```
4. **Git Security & Branch Status**:
   ```bash
   git check-ignore -v .env
   # Output: .gitignore:2:.env .env
   ```

---

## 7. Git Branch & Commits

Phase 1 development is committed on branch `phase-1-database-foundation`:
- `0f71c7b` — `feat(phase-1): database foundation and multi-tenant core models`
- `9c96778` — `docs: add phase0.md documentation`
- `cccf8ce` — `feat: initial commit for Company Command Center Phase 0 foundation`

---

## 8. Summary Status

- **Phase 1 Status**: Completed & Committed to Git branch `phase-1-database-foundation`.
- **Next Phase**: Phase 2 (Authentication, Authorization & Tenant Context Resolution Middleware).
