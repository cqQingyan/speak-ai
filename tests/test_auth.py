import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from main import app
from database import get_db, Base, engine
from models import User
from auth import get_password_hash
import asyncio

# Use an in-memory SQLite database for testing
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, class_=AsyncSession)

async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session

app.dependency_overrides[get_db] = override_get_db

@pytest_asyncio.fixture(scope="module")
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio(loop_scope="module")
async def test_register_login(setup_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Register
        response = await ac.post("/auth/register", json={
            "username": "testuser",
            "password": "testpassword",
            "email": "test@example.com"
        })
        assert response.status_code == 200
        assert "access_token" in response.json()

        # Login
        response = await ac.post("/auth/login", json={
            "username": "testuser",
            "password": "testpassword"
        })
        assert response.status_code == 200
        assert "access_token" in response.json()

        # Login Fail
        response = await ac.post("/auth/login", json={
            "username": "testuser",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
