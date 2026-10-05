# Company Command Center - Phase 2 Documentation

## 1. Overview
**Phase 2** implements the **Authentication and Multi-Tenancy Architecture** for the **Company Command Center** platform.

It adds secure multi-tenant user authentication, Argon2id password hashing, JWT access token generation and validation, stateful refresh token rotation with single-use revocation tracking, role-based access control (RBAC), tenant isolation enforcement across all user endpoints, database schema migrations for authentication fields and refresh tokens, and full end-to-end integration and unit testing suites.

---

## 2. Technical Stack & Pinned Dependencies

Phase 2 builds upon Phase 1 and introduces the following security and cryptography packages:

| Component | Choice | Pinned Version | Purpose |
|---|---|---|---|
| **Password Hashing** | passlib[argon2] / argon2-cffi | `1.7.4` / `23.1.0` | Secure password hashing using Argon2id |
| **JWT Tokens** | PyJWT[crypto] | `2.9.0` | JSON Web Token encoding, decoding, and signature verification |
| **HTTP Auth Utilities** | fastapi.security (OAuth2PasswordBearer) | FastAPI built-in | Bearer token HTTP header extraction & OpenAPI integration |

---

## 3. Directory Layout (Phase 2 Additions & Updates)

```
Company Command Center/
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   ├── config.py              # Added JWT_SECRET_KEY, algorithm, & expiration settings with validation
│   │   │   ├── database.py            # Async DB session management
│   │   │   └── security.py            # Password hashing (Argon2id), token creation, decoding & verification
│   │   ├── storage/
│   │   │   ├── models/
│   │   │   │   ├── __init__.py        # Exported RefreshToken model
│   │   │   │   ├── tenant.py          # Tenant ORM model
│   │   │   │   ├── user.py            # Added password_hash & role fields to User model
│   │   │   │   └── refresh_token.py   # RefreshToken ORM model (token_hash, revoked_at, expires_at)
│   │   ├── schemas/
│   │   │   ├── auth.py                # Pydantic schemas for Login, Register, Token, Refresh, Logout
│   │   │   └── user.py                # UserResponse, MeResponse, TenantResponse schemas
│   │   ├── services/
│   │   │   ├── auth_service.py        # Authentication logic (register, login, refresh, logout)
│   │   │   └── user_service.py        # Tenant-scoped user management logic
│   │   ├── routes/
│   │   │   ├── deps.py                # FastAPI dependencies (get_current_user, require_role)
│   │   │   ├── auth.py                # API endpoints (/auth/register, /auth/login, /auth/refresh, /auth/logout, /auth/me)
│   │   │   └── users.py               # API endpoints (/users list & create with RBAC and tenant scoping)
│   │   └── main.py                    # Registered auth and user routers
│   ├── migrations/
│   │   └── versions/
│   │       └── 2026_10_05_0001-0002_add_auth_fields_and_refresh_tokens.py # Alembic auth migration
│   └── tests/
│       ├── test_auth.py               # Unit & integration tests for authentication, tokens, & RBAC
│       ├── test_database.py           # Updated database integration tests
│       └── test_health.py             # Liveness & readiness health tests
├── phase2.md                          # Phase 2 documentation
└── README.md                          # Updated with Auth API specification & run commands
```

---

## 4. Key Architectural Implementations

### A. Core Security & JWT Management (`backend/app/core/security.py` & `config.py`)
- **Environment Validation**: `JWT_SECRET_KEY` is validated on app startup; starting without a valid secret key or with a key shorter than 32 characters raises a configuration error.
- **Argon2id Password Hashing**: Uses `passlib.context.CryptContext(schemes=["argon2"])` for state-of-the-art password security.
- **Token Generation**:
  - **Access Tokens**: Short-lived JWTs (default 30 minutes) containing claims: `sub` (User ID), `tenant_id`, `role`, `type: "access"`, and `exp`.
  - **Refresh Tokens**: Cryptographically secure 32-byte opaque strings (`secrets.token_urlsafe(32)`).
- **Refresh Token Hashing**: Stored in PostgreSQL using SHA-256 (`token_hash = hashlib.sha256(raw_token.encode()).hexdigest()`), ensuring raw refresh tokens are never persisted in plaintext.

### B. Updated Database Schema (`backend/app/storage/models/`)
1. **`User` Model Updates**:
   - `password_hash`: String(255), non-null storing Argon2id hash (`$argon2id$v=19$...`).
   - `role`: String(50), non-null, default `"member"`. Supported roles: `"owner"`, `"admin"`, `"member"`.
2. **`RefreshToken` Model (`refresh_tokens` table)**:
   - `id`: UUID (PK)
   - `user_id`: UUID (FK -> `users.id` ON DELETE CASCADE, indexed)
   - `tenant_id`: UUID (FK -> `tenants.id` ON DELETE CASCADE, indexed)
   - `token_hash`: String(64), unique, indexed, non-null (SHA-256 digest)
   - `expires_at`: `TIMESTAMPTZ`, non-null (default 7 days)
   - `revoked_at`: `TIMESTAMPTZ`, nullable (set upon logout or rotation reuse)

### C. Authentication Flow & Service Layer (`backend/app/services/auth_service.py`)
- **Tenant & Owner Registration (`POST /auth/register`)**:
  - Atomically creates a new `Tenant` and initial `User` with role `"owner"`.
  - Returns access token and raw refresh token immediately.
- **Login (`POST /auth/login`)**:
  - Validates tenant existence (`tenant_slug`), user existence (`email`), active status (`is_active` for both user and tenant), and password match (`verify_password`).
  - Mints new JWT access token and creates a active `RefreshToken` record in the database.
- **Token Refresh & Single-Use Rotation (`POST /auth/refresh`)**:
  - Hashes incoming refresh token and looks up corresponding record in `refresh_tokens`.
  - **Reuse Detection**: If a revoked refresh token is presented, all refresh tokens for that user are immediately revoked, preventing token theft compromise.
  - Revokes current token (`revoked_at = now()`), mints a brand-new access token and a brand-new refresh token (rotation).
- **Logout (`POST /auth/logout`)**:
  - Sets `revoked_at = now()` on the specified refresh token in the database.
- **User Context (`GET /auth/me`)**:
  - Returns current user details and associated tenant metadata (`MeResponse`).

### D. Multi-Tenant Authorization & RBAC (`backend/app/routes/deps.py` & `users.py`)
- **`get_current_user` Dependency**:
  - Decodes and verifies Bearer JWT token from `Authorization` header.
  - Ensures token type is `"access"` and token is not expired.
  - Fetches target user from database and verifies that user and tenant are both active.
- **`require_role(*allowed_roles)` Dependency**:
  - Enforces role-based endpoint permissions. Raises `403 Forbidden` if `current_user.role` is not in allowed roles (e.g., only `"owner"` and `"admin"` can create users).
- **Tenant Isolation Enforcement (`GET /users` & `POST /users`)**:
  - All queries are automatically filtered by `current_user.tenant_id`. Users can never view or modify records belonging to another tenant.

---

## 5. Verification & Testing

### A. Automated Test Suite (`pytest`)
- All 15 unit and integration tests executed cleanly against postgres test container:
  - `test_password_hashing_unit`: Verifies Argon2id generation and verification logic.
  - `test_jwt_token_unit`: Tests access token encoding, payload claims, expiration, and tampering rejections.
  - `test_auth_full_flow`: End-to-end integration test covering register -> me -> create user -> login -> refresh -> reuse protection -> logout.
  - `test_inactive_user_and_tenant_cannot_login`: Verifies deactivated users/tenants cannot authenticate.
  - `test_tenant_isolation_and_user_management`: Verifies strict data isolation across distinct tenant IDs.

### B. End-to-End Walkthrough Verification
Ran complete host-level verification script (`verify_phase2.py`) targeting live container (`http://localhost:8000`):
- **Tenant A Registration**: `POST /auth/register` -> `200 OK` (issued JWT & refresh token).
- **User Context**: `GET /auth/me` -> `200 OK` (retrieved user role `owner` & tenant details).
- **Member Creation**: `POST /users` -> `200 OK` (created user with role `member`).
- **Member Authorization**: `POST /users` as `member` -> `403 Forbidden` (RBAC enforced).
- **Token Rotation**: `POST /auth/refresh` -> `200 OK` (received new access token & new refresh token).
- **Reuse Protection**: Re-sending old refresh token -> `401 Unauthorized` (reuse blocked).
- **Logout**: `POST /auth/logout` -> `200 OK` (refresh token revoked).
- **Tenant Isolation**: Tenant B registration & user listing verified zero leak of Tenant A users.

### C. Database Hash Inspection
Direct psql inspection confirmed:
- Password hashes in `users` table: `$argon2id$v=19$m=65536,t=3,p=4$...`
- Refresh token hashes in `refresh_tokens` table: 64-character SHA-256 hexadecimal digests with timestamped `expires_at` and `revoked_at`.

---

## 6. Phase 2 API Specification

### 1. Register Tenant & Owner
- **`POST /auth/register`**
- **Request Body**:
  ```json
  {
    "tenant_name": "Acme Corp",
    "tenant_slug": "acme-corp",
    "email": "owner@acme.com",
    "full_name": "Acme Owner",
    "password": "SecurePassword123!"
  }
  ```
- **Response (`200 OK`)**:
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1Ni...",
    "refresh_token": "a8f9d0c2e...",
    "token_type": "bearer",
    "expires_in": 1800
  }
  ```

### 2. User Login
- **`POST /auth/login`**
- **Request Body**:
  ```json
  {
    "tenant_slug": "acme-corp",
    "email": "owner@acme.com",
    "password": "SecurePassword123!"
  }
  ```
- **Response (`200 OK`)**: Same `TokenResponse` format as register.

### 3. Current User Context
- **`GET /auth/me`**
- **Headers**: `Authorization: Bearer <access_token>`
- **Response (`200 OK`)**:
  ```json
  {
    "user": {
      "id": "uuid",
      "tenant_id": "uuid",
      "email": "owner@acme.com",
      "full_name": "Acme Owner",
      "role": "owner",
      "is_active": true,
      "created_at": "2026-10-05T19:00:00Z",
      "updated_at": "2026-10-05T19:00:00Z"
    },
    "tenant": {
      "id": "uuid",
      "name": "Acme Corp",
      "slug": "acme-corp",
      "is_active": true,
      "created_at": "2026-10-05T19:00:00Z",
      "updated_at": "2026-10-05T19:00:00Z"
    }
  }
  ```

### 4. Refresh Tokens
- **`POST /auth/refresh`**
- **Request Body**: `{"refresh_token": "<raw_refresh_token>"}`
- **Response (`200 OK`)**: Rotated `TokenResponse` with new access token and new refresh token.

### 5. Logout
- **`POST /auth/logout`**
- **Request Body**: `{"refresh_token": "<raw_refresh_token>"}`
- **Response (`200 OK`)**: `{"status": "logged_out"}`

### 6. User Management (Tenant Scoped & RBAC Restricted)
- **`GET /users`**: List all users within current tenant. Requires valid bearer token.
- **`POST /users`**: Create a user within current tenant. Requires `owner` or `admin` role.
