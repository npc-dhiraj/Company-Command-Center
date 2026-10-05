# Authentication & Multi-Tenant Identity Architecture

This document describes the authentication, token management, and tenant resolution architecture implemented in Phase 2 of the Company Command Center project.

---

## 1. Authentication Flows

### Register (`POST /auth/register`)
- **Input**: `tenant_name`, `tenant_slug`, `email`, `full_name`, `password` (minimum 12 characters).
- **Behavior**:
  - Validates `tenant_slug` format (lowercase letters, digits, hyphens).
  - Verifies `tenant_slug` is unique.
  - Creates the `Tenant` record and initial `User` record with role `owner` in **ONE single database transaction**.
  - Generates an Access Token and an opaque Refresh Token.
  - Stores SHA-256 hash of the refresh token in the database.
- **Output**: `access_token`, `refresh_token`, `token_type` ("bearer").

### Login (`POST /auth/login`)
- **Input**: `tenant_slug`, `email`, `password`.
- **Behavior**:
  - Identifies tenant by `tenant_slug`.
  - Identifies user within tenant by `email`.
  - Verifies user's hashed password using Argon2id.
  - Re-hashes password automatically if Argon2 parameters have been upgraded (`check_needs_rehash`).
  - Checks `is_active` on both tenant and user.
  - Generates new Access Token and rotating Refresh Token pair on success.
- **Output**: `access_token`, `refresh_token`, `token_type` ("bearer").

### Token Refresh (`POST /auth/refresh`)
- **Input**: `refresh_token` (opaque string).
- **Behavior**:
  - Hashes the input token using SHA-256 and searches for matching record in `refresh_tokens`.
  - Validates token is not expired and `revoked_at` is `NULL`.
  - **Token Rotation**: Revokes the used refresh token immediately (`revoked_at = now()`) and issues a brand-new access/refresh token pair.
  - Reusing a revoked token fails immediately with `401 Unauthorized`.
- **Output**: New `access_token`, new `refresh_token`, `token_type` ("bearer").

### Logout (`POST /auth/logout`)
- **Input**: `refresh_token` (opaque string).
- **Behavior**:
  - Hashes token and sets `revoked_at = now()` on the corresponding record.
  - **Idempotent**: Calling logout multiple times with the same token does not raise an error.
- **Output**: `{"status": "logged_out"}`.

### Current User Info (`GET /auth/me`)
- **Header**: `Authorization: Bearer <access_token>`
- **Behavior**: Decodes JWT, validates active status of user and tenant, and returns user profile and tenant details.

---

## 2. Token Lifetimes & Security

| Token Type | Storage Format | Expiration | Purpose |
| :--- | :--- | :--- | :--- |
| **Access Token** | JWT (HS256) | 15 Minutes (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`) | API Request Authorization |
| **Refresh Token** | Opaque String (`secrets.token_urlsafe(32)`), stored **HASHED (SHA-256)** in DB | 7 Days (configurable via `REFRESH_TOKEN_EXPIRE_DAYS`) | Obtaining fresh Access & Refresh tokens |

---

## 3. Roles & Permissions

Users are assigned one of three enum roles (`UserRole`):
- `owner`: Full privileges within the tenant, including creating `admin` and `member` users.
- `admin`: Operational privileges within the tenant. Can create `member` users, but **cannot create owners**.
- `member`: Regular tenant user. Read access to tenant data, cannot invoke management endpoints (e.g. `POST /users` returns `403 Forbidden`).

---

## 4. Tenant Resolution & Isolation

- **Tenant-from-Token Rule**: Tenant identity comes **ONLY** from the verified JWT claim (`tenant_id`).
- Requests never accept or trust `tenant_id` from request bodies, query parameters, or custom HTTP headers.
- Services explicitly receive `tenant_id` from the authenticated `current_user` object.
- Queries across the application strictly filter data by `tenant_id` (e.g., `WHERE tenant_id = :caller_tenant_id`).

---

## 5. Security Protections & Mitigations

1. **Password Hashing**: Powered by Argon2id (`argon2-cffi`). Plaintext passwords are never logged or stored.
2. **Generic Credentials Errors**: All login failures return `401 Unauthorized` with the generic message `"Invalid credentials"`.
3. **Timing Attack Protection**: When a tenant or email is not found during login attempts, a dummy Argon2 password check is performed so response timings remain consistent regardless of user existence.
4. **Token Security**: Raw refresh tokens are never written to disk or database logs; only SHA-256 hashes are stored. Passwords, hashes, and raw tokens are excluded from all Pydantic response models.
