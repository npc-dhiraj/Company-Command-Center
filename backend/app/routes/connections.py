"""Connection and connector routes.

Routes stay thin — all business logic lives in the service layer.
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.registry import list_connectors
from app.core.database import get_session
from app.routes.deps import get_current_user, require_role
from app.schemas.connection import (
    ConnectionCreateRequest,
    ConnectionResponse,
    ConnectorInfoResponse,
)
from app.services.connection_service import (
    create_connection,
    delete_connection,
    get_connection,
    list_connections,
    test_connection_by_id,
)
from app.storage.models import User, UserRole

router = APIRouter(tags=["connectors"])


# ---------- Connector metadata (provider types) ----------


def _credential_fields(schema: type) -> list[dict[str, str]]:
    """Extract field names and types from a Pydantic model."""
    fields: list[dict[str, str]] = []
    for name, info in schema.model_fields.items():
        annotation = info.annotation
        type_name = getattr(annotation, "__name__", str(annotation))
        fields.append({"name": name, "type": type_name})
    return fields


@router.get("/connectors", response_model=list[ConnectorInfoResponse])
async def list_connector_types(
    _current_user: User = Depends(get_current_user),
) -> list[ConnectorInfoResponse]:
    """List registered connector providers with metadata and credential field info."""
    result: list[ConnectorInfoResponse] = []
    for _key, cls in list_connectors().items():
        meta = cls.metadata
        result.append(
            ConnectorInfoResponse(
                provider_key=meta.provider_key,
                display_name=meta.display_name,
                description=meta.description,
                category=meta.category.value,
                credential_fields=_credential_fields(cls.credentials_schema),
            )
        )
    return result


# ---------- Connection CRUD ----------


@router.post("/connections", response_model=ConnectionResponse)
async def create_connection_endpoint(
    req: ConnectionCreateRequest,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> ConnectionResponse:
    conn = await create_connection(
        session=session,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        provider=req.provider,
        name=req.name,
        raw_credentials=req.credentials,
        config=req.config,
    )
    return ConnectionResponse.model_validate(conn)


@router.get("/connections", response_model=list[ConnectionResponse])
async def list_connections_endpoint(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ConnectionResponse]:
    conns = await list_connections(session, current_user.tenant_id)
    return [ConnectionResponse.model_validate(c) for c in conns]


@router.get("/connections/{connection_id}", response_model=ConnectionResponse)
async def get_connection_endpoint(
    connection_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConnectionResponse:
    conn = await get_connection(session, current_user.tenant_id, connection_id)
    return ConnectionResponse.model_validate(conn)


@router.post(
    "/connections/{connection_id}/test", response_model=ConnectionResponse
)
async def test_connection_endpoint(
    connection_id: UUID,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> ConnectionResponse:
    conn = await test_connection_by_id(session, current_user.tenant_id, connection_id)
    return ConnectionResponse.model_validate(conn)


@router.delete("/connections/{connection_id}", status_code=204)
async def delete_connection_endpoint(
    connection_id: UUID,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> None:
    await delete_connection(session, current_user.tenant_id, connection_id)
