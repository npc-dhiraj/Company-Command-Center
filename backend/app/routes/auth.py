from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.routes.deps import get_current_user
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.user import MeResponse, TenantResponse, UserResponse
from app.services.auth_service import (
    login_user,
    logout_user,
    refresh_tokens,
    register_tenant_and_owner,
)
from app.storage.models import Tenant, User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
async def register(
    req: RegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    return await register_tenant_and_owner(session, req)


@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    return await login_user(session, req)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    req: RefreshRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    return await refresh_tokens(session, req.refresh_token)


@router.post("/logout")
async def logout(
    req: LogoutRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    await logout_user(session, req.refresh_token)
    return {"status": "logged_out"}


@router.get("/me", response_model=MeResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MeResponse:
    res = await session.execute(
        select(Tenant).where(Tenant.id == current_user.tenant_id)
    )
    tenant = res.scalar_one()
    return MeResponse(
        user=UserResponse.model_validate(current_user),
        tenant=TenantResponse.model_validate(tenant),
    )
