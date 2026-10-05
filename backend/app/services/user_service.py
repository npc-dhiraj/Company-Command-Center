from collections.abc import Sequence
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.schemas.user import UserCreateRequest
from app.storage.models import User, UserRole


async def create_user_for_tenant(
    session: AsyncSession,
    tenant_id: UUID,
    caller_role: UserRole,
    req: UserCreateRequest,
) -> User:
    if caller_role == UserRole.ADMIN and req.role == UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins cannot create owners",
        )

    res = await session.execute(
        select(User).where(User.tenant_id == tenant_id, User.email == req.email)
    )
    if res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists in this tenant",
        )

    user = User(
        tenant_id=tenant_id,
        email=req.email,
        full_name=req.full_name,
        password_hash=hash_password(req.password),
        role=req.role,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def list_users_for_tenant(
    session: AsyncSession, tenant_id: UUID
) -> Sequence[User]:
    res = await session.execute(select(User).where(User.tenant_id == tenant_id))
    return res.scalars().all()
