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

## 5. Argon2 Password Hashing
- **Decision**: Use Argon2id (`argon2-cffi`) for all password hashing.
- **Rationale**: Argon2id is the memory-hard password hashing standard recommended by OWASP, resistant to GPU/ASIC cracking and side-channel attacks. Includes automatic rehash support.

## 6. JWT & Rotating Hashed Refresh Tokens
- **Decision**: Issue short-lived JWT access tokens (15-minute default) signed with HS256, paired with opaque random refresh tokens stored hashed (SHA-256) in PostgreSQL for 7 days and rotated on every use.
- **Rationale**: Short-lived JWTs limit exposure windows. Storing refresh tokens hashed prevents token theft via database leaks. Token rotation invalidates compromised tokens upon reuse attempts.

## 7. Tenant-From-Token Identity Rule
- **Decision**: Tenant identity is strictly derived from the verified `tenant_id` claim in the authenticated JWT. Tenant IDs in request bodies, query params, or headers are never trusted.
- **Rationale**: Eliminates multi-tenant identity spoofing vulnerabilities by enforcing identity scoping at the authentication boundary.

## 8. Row-Level Security (RLS) Deferred
- **Decision**: PostgreSQL Row-Level Security (RLS) is deferred in Phase 2; tenant isolation is currently enforced application-side in service layers.
- **Rationale**: Keeps early database migrations simple while maintaining application-level tenant isolation. **Must revisit and implement native Postgres RLS before storing real customer data.**

## 9. Login Rate Limiting Deferred
- **Decision**: Authentication rate limiting (e.g. IP/account brute-force throttling) is deferred in Phase 2.
- **Rationale**: Focuses scope on core authentication and tenancy structures. Timing attack mitigation via dummy password verification is implemented, with rate limiting scheduled for pre-production deployment.
