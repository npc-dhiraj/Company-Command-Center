import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.database import get_session
from app.main import app
from app.storage.base import Base

TEST_DB_NAME = os.getenv("POSTGRES_DB_TEST", "company_command_center_test")
TEST_DATABASE_URL = (
    f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
    f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{TEST_DB_NAME}"
)


@pytest_asyncio.fixture
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
    try:
        async with engine.begin() as conn:

            def drop_tables(sync_conn: Connection) -> None:
                Base.metadata.drop_all(sync_conn)

            def create_tables(sync_conn: Connection) -> None:
                Base.metadata.create_all(sync_conn)

            await conn.run_sync(drop_tables)
            await conn.run_sync(create_tables)
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(autouse=True)
async def override_get_session(db_session: AsyncSession) -> AsyncGenerator[None, None]:
    async def _get_test_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.clear()
