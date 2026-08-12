import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from main import app

TEST_DATABASE_URL = "postgresql+asyncpg://journal_test:testpassword@localhost:5433/journal_test"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def override_get_db():
    async with TestSessionLocal() as session:
        yield session

app.dependency_overrides[get_db] = override_get_db

@pytest_asyncio.fixture(autouse=True)
async def reset_rate_limiter():
    from app.limiter import limiter
    limiter._storage.reset()
    yield

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture(autouse=True)
async def clean_tables():
    yield
    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())

@pytest_asyncio.fixture(autouse=True)
async def mock_email():
    with patch("app.routers.users.send_verification_email", new_callable=AsyncMock):
        yield

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

@pytest_asyncio.fixture
async def auth_client(client):
    await client.post("/api/users/register", json={
        "email": "test@example.com",
        "username": "testuser",
        "password": "testpassword123"
    })
    from sqlalchemy import update
    from app import models
    async with TestSessionLocal() as db:
        await db.execute(
            update(models.User)
            .where(models.User.email == "test@example.com")
            .values(is_verified=True)
        )
        await db.commit()
    res = await client.post("/api/users/login", data={
        "username": "test@example.com",
        "password": "testpassword123"
    })
    token = res.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client
