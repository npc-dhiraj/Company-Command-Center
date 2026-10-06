"""Fake connector used exclusively in tests.

This connector is NEVER registered in the production registry.
Tests register it via a fixture and clean up after themselves.
"""

from typing import Any

from pydantic import BaseModel, Field

from app.connectors.base import (
    BaseConnector,
    ConnectorCategory,
    ConnectorError,
    ConnectorMetadata,
)


class FakeCredentials(BaseModel):
    """Credentials schema for the fake test connector."""

    api_key: str = Field(..., min_length=1)


class FakeConnector(BaseConnector):
    """A minimal connector for testing purposes.

    - Accepts credentials with an ``api_key`` field.
    - ``test_connection`` fails when ``api_key == "bad"``.
    - ``test_connection`` hangs (for timeout testing) when ``api_key == "timeout"``.
    """

    metadata = ConnectorMetadata(
        provider_key="fake",
        display_name="Fake Connector",
        description="A test-only connector that does nothing real",
        category=ConnectorCategory.OTHER,
    )
    credentials_schema = FakeCredentials

    async def validate_credentials(self, raw: dict[str, Any]) -> FakeCredentials:
        try:
            return FakeCredentials(**raw)
        except Exception:
            raise ConnectorError("Invalid credentials: 'api_key' is required") from None

    async def test_connection(self, credentials: BaseModel) -> None:
        assert isinstance(credentials, FakeCredentials)
        if credentials.api_key == "bad":
            raise ConnectorError("Connection test failed: invalid API key")
        if credentials.api_key == "timeout":
            import asyncio

            await asyncio.sleep(60)  # Will be caught by the 10s timeout
