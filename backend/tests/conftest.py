import os

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base

TEST_DB = os.environ.get("TEST_DATABASE_URL", "postgresql+asyncpg://mynews:mynews@localhost:5432/mynews_test")


@pytest_asyncio.fixture
async def session():
    """Sesión sobre Postgres+pgvector real; el esquema se recrea en cada test."""
    try:
        engine = create_async_engine(TEST_DB)
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    except OSError:
        pytest.skip("no hay PostgreSQL disponible (define TEST_DATABASE_URL)")
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()
