# Architectural Decisions

## 1. Multi-Tenancy Strategy
- **Approach**: Shared Database, Shared Schema with Logical Isolation.
- **Data Isolation**: Every application table will include a mandatory `tenant_id` foreign key column indexed for query optimization.
- **Application Security**: Query construction and ORM layers will strictly enforce `tenant_id` filtering on all data access requests.
- **Rationale**: This design provides optimal resource efficiency, simpler database migrations, and operational scalability for initial multi-tenant rollouts.

## 2. Async SQLAlchemy 2.x Architecture
- **Decision**: Use SQLAlchemy 2.x in async mode with the `asyncpg` driver for application database interactions.
- **Rationale**: Non-blocking I/O ensures high concurrency and low latency for FastAPI endpoints processing multiple tenant requests concurrently.

## 3. UUID Primary Keys
- **Decision**: Use application-generated UUID v4 keys (`UUIDPrimaryKeyMixin`) for all database tables.
- **Rationale**: Prevents ID enumeration attacks, allows client-side ID generation before insertion, and simplifies distributed data merging or future sharding across systems.

## 4. Explicit Migrations Engine
- **Decision**: Execute database migrations explicitly via `alembic upgrade head` rather than auto-running migrations on container initialization.
- **Rationale**: Prevents race conditions during multi-instance container deployments and gives operators explicit control over database schema transitions.
