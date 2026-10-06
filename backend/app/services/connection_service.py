"""Connection management service.

All methods receive the tenant_id explicitly (derived from the
authenticated user in the route layer).  Credentials are encrypted
at rest and never returned, logged, or included in error messages.
"""

import asyncio
import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import ConnectorError
from app.connectors.registry import get_connector
from app.core.crypto import decrypt_json, encrypt_json
from app.storage.models import Connection, ConnectionStatus

logger = logging.getLogger(__name__)

# Timeout for connector test_connection calls (seconds)
_TEST_TIMEOUT_SECONDS = 10


async def create_connection(
    session: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    provider: str,
    name: str,
    raw_credentials: dict[str, Any],
    config: dict[str, Any],
) -> Connection:
    """Create a new connection after validating and testing credentials."""
    # Look up the connector
    try:
        connector_cls = get_connector(provider)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown connector provider: '{provider}'",
        ) from None

    connector = connector_cls()

    # Validate credentials through the connector
    try:
        validated = await connector.validate_credentials(raw_credentials)
    except ConnectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.safe_message,
        ) from None

    # Test the connection
    try:
        await asyncio.wait_for(
            connector.test_connection(validated),
            timeout=_TEST_TIMEOUT_SECONDS,
        )
    except ConnectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.safe_message,
        ) from None
    except TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Connection test timed out",
        ) from None
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Connection test failed unexpectedly",
        ) from None

    # Encrypt credentials and store
    encrypted = encrypt_json(raw_credentials)

    connection = Connection(
        tenant_id=tenant_id,
        provider=provider,
        name=name,
        status=ConnectionStatus.ACTIVE,
        encrypted_credentials=encrypted,
        config=config,
        last_tested_at=datetime.now(UTC),
        created_by_user_id=user_id,
    )
    session.add(connection)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        # Unique constraint violation → duplicate (tenant, provider, name)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"A connection named '{name}' already exists "
                f"for provider '{provider}'"
            ),
        ) from None
    await session.refresh(connection)
    return connection


async def list_connections(
    session: AsyncSession,
    tenant_id: UUID,
) -> Sequence[Connection]:
    """List all connections belonging to the given tenant."""
    result = await session.execute(
        select(Connection).where(Connection.tenant_id == tenant_id)
    )
    return result.scalars().all()


async def get_connection(
    session: AsyncSession,
    tenant_id: UUID,
    connection_id: UUID,
) -> Connection:
    """Get a single connection by ID, scoped to the tenant.

    Returns 404 for both missing and other-tenant connections
    so existence is never leaked.
    """
    result = await session.execute(
        select(Connection).where(
            Connection.id == connection_id,
            Connection.tenant_id == tenant_id,
        )
    )
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found",
        )
    return connection


async def delete_connection(
    session: AsyncSession,
    tenant_id: UUID,
    connection_id: UUID,
) -> None:
    """Hard-delete a connection, destroying stored credentials."""
    connection = await get_connection(session, tenant_id, connection_id)
    await session.delete(connection)
    await session.commit()


async def test_connection_by_id(
    session: AsyncSession,
    tenant_id: UUID,
    connection_id: UUID,
) -> Connection:
    """Decrypt credentials in memory, run the connector test, and update status."""
    connection = await get_connection(session, tenant_id, connection_id)

    try:
        connector_cls = get_connector(connection.provider)
    except KeyError:
        connection.status = ConnectionStatus.ERROR
        connection.last_tested_at = datetime.now(UTC)
        connection.last_error = "Connector provider is no longer available"
        session.add(connection)
        await session.commit()
        await session.refresh(connection)
        return connection

    connector = connector_cls()

    # Decrypt credentials in memory
    try:
        raw_creds = decrypt_json(connection.encrypted_credentials)
    except ValueError:
        connection.status = ConnectionStatus.ERROR
        connection.last_tested_at = datetime.now(UTC)
        connection.last_error = "Stored credentials could not be decrypted"
        session.add(connection)
        await session.commit()
        await session.refresh(connection)
        return connection

    # Validate and test
    try:
        validated = await connector.validate_credentials(raw_creds)
        await asyncio.wait_for(
            connector.test_connection(validated),
            timeout=_TEST_TIMEOUT_SECONDS,
        )
        connection.status = ConnectionStatus.ACTIVE
        connection.last_error = None
    except ConnectorError as exc:
        connection.status = ConnectionStatus.ERROR
        connection.last_error = exc.safe_message
    except TimeoutError:
        connection.status = ConnectionStatus.ERROR
        connection.last_error = "Connection test timed out"
    except Exception:
        connection.status = ConnectionStatus.ERROR
        connection.last_error = "Connection test failed unexpectedly"

    connection.last_tested_at = datetime.now(UTC)
    session.add(connection)
    await session.commit()
    await session.refresh(connection)
    return connection
