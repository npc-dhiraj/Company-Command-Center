from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Connection, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.database import get_session
from app.main import app
from app.storage.models import Tenant, User


@pytest.mark.db
@pytest.mark.asyncio
async def test_tables_exist(test_engine: AsyncEngine) -> None:
    async with test_engine.connect() as conn:

        def get_tables(sync_conn: Connection) -> list[str]:
            inspector = inspect(sync_conn)
            return inspector.get_table_names()

        tables = await conn.run_sync(get_tables)
        assert "tenants" in tables
        assert "users" in tables


@pytest.mark.db
@pytest.mark.asyncio
async def test_create_tenant_and_user(db_session: AsyncSession) -> None:
    tenant = Tenant(name="Acme Corp", slug="acme")
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)

    assert tenant.id is not None
    assert tenant.name == "Acme Corp"
    assert tenant.is_active is True

    user = User(
        tenant_id=tenant.id,
        email="alice@acme.com",
        full_name="Alice Smith",
        password_hash="dummy_hash",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert user.id is not None
    assert user.tenant_id == tenant.id
    assert user.email == "alice@acme.com"


@pytest.mark.db
@pytest.mark.asyncio
async def test_duplicate_tenant_email_rejected(db_session: AsyncSession) -> None:
    tenant = Tenant(name="Stark Industries", slug="stark")
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)

    user1 = User(
        tenant_id=tenant.id,
        email="tony@stark.com",
        full_name="Tony Stark",
        password_hash="dummy_hash",
    )
    db_session.add(user1)
    await db_session.commit()

    user2 = User(
        tenant_id=tenant.id,
        email="tony@stark.com",
        full_name="Tony Duplicate",
        password_hash="dummy_hash",
    )
    db_session.add(user2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.db
@pytest.mark.asyncio
async def test_same_email_different_tenants_allowed(db_session: AsyncSession) -> None:
    tenant1 = Tenant(name="Wayne Enterprises", slug="wayne")
    tenant2 = Tenant(name="Queen Industries", slug="queen")
    db_session.add_all([tenant1, tenant2])
    await db_session.commit()
    await db_session.refresh(tenant1)
    await db_session.refresh(tenant2)

    user1 = User(
        tenant_id=tenant1.id,
        email="ceo@hero.com",
        full_name="Bruce Wayne",
        password_hash="dummy_hash",
    )
    user2 = User(
        tenant_id=tenant2.id,
        email="ceo@hero.com",
        full_name="Oliver Queen",
        password_hash="dummy_hash",
    )
    db_session.add_all([user1, user2])
    await db_session.commit()

    res1 = await db_session.execute(select(User).where(User.tenant_id == tenant1.id))
    res2 = await db_session.execute(select(User).where(User.tenant_id == tenant2.id))
    assert res1.scalar_one().full_name == "Bruce Wayne"
    assert res2.scalar_one().full_name == "Oliver Queen"


@pytest.mark.db
@pytest.mark.asyncio
async def test_readiness_check_success(db_session: AsyncSession) -> None:
    async def mock_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = mock_get_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/health/ready")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
