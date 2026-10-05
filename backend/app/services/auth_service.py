from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_dummy_password,
    verify_password,
)
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.storage.models import RefreshToken, Tenant, User, UserRole


async def register_tenant_and_owner(
    session: AsyncSession, req: RegisterRequest
) -> TokenResponse:
    res = await session.execute(select(Tenant).where(Tenant.slug == req.tenant_slug))
    if res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant slug already registered",
        )

    tenant = Tenant(name=req.tenant_name, slug=req.tenant_slug)
    session.add(tenant)
    await session.flush()

    user = User(
        tenant_id=tenant.id,
        email=req.email,
        full_name=req.full_name,
        password_hash=hash_password(req.password),
        role=UserRole.OWNER,
    )
    session.add(user)
    await session.flush()

    raw_refresh_token = generate_refresh_token()
    token_hash = hash_refresh_token(raw_refresh_token)
    expires_at = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    refresh_record = RefreshToken(
        tenant_id=tenant.id,
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    session.add(refresh_record)
    await session.commit()

    access_token = create_access_token(
        user_id=user.id,
        tenant_id=tenant.id,
        role=user.role,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh_token,
    )


async def login_user(session: AsyncSession, req: LoginRequest) -> TokenResponse:
    t_res = await session.execute(select(Tenant).where(Tenant.slug == req.tenant_slug))
    tenant = t_res.scalar_one_or_none()
    if not tenant or not tenant.is_active:
        verify_dummy_password()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    u_res = await session.execute(
        select(User).where(User.tenant_id == tenant.id, User.email == req.email)
    )
    user = u_res.scalar_one_or_none()
    if not user or not user.is_active:
        verify_dummy_password()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    is_valid, new_hash = verify_password(req.password, user.password_hash)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if new_hash:
        user.password_hash = new_hash
        session.add(user)

    raw_refresh_token = generate_refresh_token()
    token_hash = hash_refresh_token(raw_refresh_token)
    expires_at = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    refresh_record = RefreshToken(
        tenant_id=tenant.id,
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    session.add(refresh_record)
    await session.commit()

    access_token = create_access_token(
        user_id=user.id,
        tenant_id=tenant.id,
        role=user.role,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh_token,
    )


async def refresh_tokens(
    session: AsyncSession, raw_refresh_token: str
) -> TokenResponse:
    token_hash = hash_refresh_token(raw_refresh_token)
    res = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    token_record = res.scalar_one_or_none()
    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    now = datetime.now(UTC)
    if token_record.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
        )

    if token_record.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )

    u_res = await session.execute(select(User).where(User.id == token_record.user_id))
    user = u_res.scalar_one_or_none()
    t_res = await session.execute(
        select(Tenant).where(Tenant.id == token_record.tenant_id)
    )
    tenant = t_res.scalar_one_or_none()

    if not user or not user.is_active or not tenant or not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User or tenant is inactive",
        )

    token_record.revoked_at = now
    session.add(token_record)

    new_raw_token = generate_refresh_token()
    new_token_hash = hash_refresh_token(new_raw_token)
    new_expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    new_refresh_record = RefreshToken(
        tenant_id=tenant.id,
        user_id=user.id,
        token_hash=new_token_hash,
        expires_at=new_expires_at,
    )
    session.add(new_refresh_record)
    await session.commit()

    access_token = create_access_token(
        user_id=user.id,
        tenant_id=tenant.id,
        role=user.role,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_raw_token,
    )


async def logout_user(session: AsyncSession, raw_refresh_token: str) -> None:
    token_hash = hash_refresh_token(raw_refresh_token)
    res = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    token_record = res.scalar_one_or_none()
    if token_record and token_record.revoked_at is None:
        token_record.revoked_at = datetime.now(UTC)
        session.add(token_record)
        await session.commit()
