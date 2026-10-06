"""Pydantic schemas for connection endpoints.

Credentials are represented as ``SecretStr`` in memory and are NEVER
included in any response schema.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ConnectionCreateRequest(BaseModel):
    """Request body for creating a new connection."""

    provider: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    credentials: dict[str, Any] = Field(
        ..., description="Raw credential key-value pairs (never stored in plaintext)"
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Non-secret configuration settings",
    )


class ConnectionResponse(BaseModel):
    """Response body for connection endpoints.

    Credentials and ciphertext are NEVER included.
    """

    id: UUID
    tenant_id: UUID
    provider: str
    name: str
    status: str
    config: dict[str, Any]
    last_tested_at: datetime | None
    last_error: str | None
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConnectorInfoResponse(BaseModel):
    """Metadata about a registered connector provider."""

    provider_key: str
    display_name: str
    description: str
    category: str
    credential_fields: list[dict[str, str]] = Field(
        ..., description="Required credential field names and types"
    )
