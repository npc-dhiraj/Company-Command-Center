# Connector Framework

This document describes the connector SDK, how to implement new connectors, and the security rules governing credential handling.

---

## 1. Overview

The connector framework provides a standard interface for integrating external services into the Company Command Center. In Phase 3, only the framework itself is implemented — **no real integrations exist yet**. A test-only `FakeConnector` is used to validate the framework.

Connectors are identified by a stable string key (e.g. `"slack"`, `"github"`), stored as a plain string column — adding a new connector never requires a database migration.

---

## 2. Connector Interface

Every connector must subclass `BaseConnector` (defined in `app/connectors/base.py`) and provide:

### Class Attributes

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `metadata` | `ConnectorMetadata` | Provider key, display name, description, category |
| `credentials_schema` | `type[BaseModel]` | Pydantic model describing required credential fields |

### Required Methods

| Method | Signature | Description |
| :--- | :--- | :--- |
| `validate_credentials` | `async (raw: dict) -> BaseModel` | Parse and validate raw credential dicts. Raise `ConnectorError` on failure. |
| `test_connection` | `async (credentials: BaseModel) -> None` | Verify connectivity. Raise `ConnectorError` with a **safe** message on failure. |

### ConnectorMetadata Fields

- `provider_key`: Unique string identifier (e.g. `"slack"`)
- `display_name`: Human-readable name (e.g. `"Slack"`)
- `description`: Short description of the connector
- `category`: One of `communication`, `development`, `productivity`, `meetings`, `crm`, `support`, `monitoring`, `other`

---

## 3. How to Add a New Connector

### Step 1: Create the connector module

Create a new file in `app/connectors/` (e.g. `app/connectors/slack.py`):

```python
from typing import Any
from pydantic import BaseModel, Field
from app.connectors.base import (
    BaseConnector, ConnectorCategory, ConnectorError, ConnectorMetadata,
)

class SlackCredentials(BaseModel):
    bot_token: str = Field(..., min_length=1)

class SlackConnector(BaseConnector):
    metadata = ConnectorMetadata(
        provider_key="slack",
        display_name="Slack",
        description="Connect to Slack workspaces",
        category=ConnectorCategory.COMMUNICATION,
    )
    credentials_schema = SlackCredentials

    async def validate_credentials(self, raw: dict[str, Any]) -> SlackCredentials:
        try:
            return SlackCredentials(**raw)
        except Exception:
            raise ConnectorError("Invalid Slack credentials")

    async def test_connection(self, credentials: BaseModel) -> None:
        assert isinstance(credentials, SlackCredentials)
        # Call Slack API to verify the token works
        # raise ConnectorError("...safe message...") on failure
```

### Step 2: Register the connector

In `app/connectors/__init__.py`, import and register:

```python
from app.connectors.registry import register_connector
from app.connectors.slack import SlackConnector

register_connector(SlackConnector)
```

### Step 3: That's it

No migration needed. The new provider key will appear in `GET /connectors` and can be used in `POST /connections`.

---

## 4. Credential Handling Rules

These rules are **non-negotiable** for all connector implementations:

1. **Credentials are encrypted at rest** using Fernet symmetric encryption. They are stored as a single encrypted JSON blob in the `encrypted_credentials` column.
2. **Credentials are NEVER returned by any API endpoint.** The `ConnectionResponse` schema deliberately excludes them.
3. **Credentials are NEVER logged.** Not in application logs, not in error messages, not in exception tracebacks.
4. **Credentials are NEVER included in exception messages.** Use `ConnectorError` with a safe, user-displayable message.
5. **Credentials are NEVER stored in the `config` column.** The `config` JSONB column is for non-secret settings only (e.g. sync interval, channel filter).
6. **In memory, credential fields use Pydantic `SecretStr`** where appropriate to prevent accidental logging via `repr()`.
7. **The `ENCRYPTION_KEY` environment variable is required** — the application will refuse to start without a valid Fernet key.

### Generating an Encryption Key

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## 5. API Endpoints

| Endpoint | Method | Access | Description |
| :--- | :--- | :--- | :--- |
| `/connectors` | `GET` | Authenticated | List registered connector types with metadata and credential field info |
| `/connections` | `POST` | Owner/Admin | Create a new connection (validates + tests credentials first) |
| `/connections` | `GET` | Authenticated | List connections for caller's tenant |
| `/connections/{id}` | `GET` | Authenticated | Get a single connection (own tenant only) |
| `/connections/{id}/test` | `POST` | Owner/Admin | Re-test a connection, updating status |
| `/connections/{id}` | `DELETE` | Owner/Admin | Hard-delete a connection and its credentials |

---

## 6. Connection Statuses

| Status | Meaning |
| :--- | :--- |
| `active` | Connection is working correctly |
| `error` | Last test failed (see `last_error` for safe details) |
| `disabled` | Manually disabled by the user |
