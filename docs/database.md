# Database Architecture & Conventions

## 1. Conventions
- **Primary Keys**: Every table uses a UUID v4 primary key generated application-side (`uuid4()`).
- **Timestamps**: All timestamps are timezone-aware UTC datetimes (`DateTime(timezone=True)` / `TIMESTAMPTZ`), with `server_default=func.now()`.
- **Multi-Tenancy**: Every tenant-owned table must inherit `TenantOwnedMixin`, providing a non-null, indexed `tenant_id` foreign key referencing `tenants.id` with `ON DELETE CASCADE`.
- **Constraint Naming**: Explicit constraint naming convention is enforced across all models (`pk_%`, `fk_%`, `uq_%`, `ix_%`, `ck_%`) to guarantee deterministic Alembic migrations.

---

## 2. Managing Migrations with Alembic

Migrations are generated and executed **explicitly**. They do NOT automatically run on container startup.

### Generating Migrations
```bash
docker compose exec backend alembic revision --autogenerate -m "description_of_change"
```

### Applying Migrations
Apply all pending migrations up to `head`:
```bash
docker compose exec backend alembic upgrade head
```

### Rolling Back Migrations
Roll back the most recent migration step:
```bash
docker compose exec backend alembic downgrade -1
```

Roll back all migrations to base state:
```bash
docker compose exec backend alembic downgrade base
```

---

## 3. Database Testing

The test suite distinguishes between fast non-database unit tests and database integration tests:

### Running Non-DB Tests
```bash
pytest -m "not db"
```

### Running All Tests (Including DB Integration)
```bash
pytest
```
*(Requires a running PostgreSQL instance and `company_command_center_test` database).*
