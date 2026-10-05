from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.routes.deps import get_current_user, require_role
from app.schemas.user import UserCreateRequest, UserResponse
from app.services.user_service import create_user_for_tenant, list_users_for_tenant
from app.storage.models import User, UserRole

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserResponse)
async def create_user(
    req: UserCreateRequest,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    user = await create_user_for_tenant(
        session, current_user.tenant_id, current_user.role, req
    )
    return UserResponse.model_validate(user)


@router.get("", response_model=list[UserResponse])
async def list_users(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[UserResponse]:
    users = await list_users_for_tenant(session, current_user.tenant_id)
    return [UserResponse.model_validate(u) for u in users]
