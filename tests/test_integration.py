import pytest
from httpx import AsyncClient, Response
import respx

@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_auth_flow(client: AsyncClient):
    # Register
    response = await client.post("/api/auth/register", json={
        "username": "testuser",
        "password": "testpassword"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    token = data["access_token"]

    # Login
    response = await client.post("/api/auth/token", data={
        "username": "testuser",
        "password": "testpassword"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()

    # Access Protected Route without token
    response = await client.post("/api/process_text", json={"text": "Hello"}, headers={})
    assert response.status_code == 401
