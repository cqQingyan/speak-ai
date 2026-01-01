import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_auth_flow(client: AsyncClient):
    # 1. Register
    response = await client.post("/auth/register", json={
        "username": "testuser",
        "email": "test@test.com",
        "password": "strongpassword"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    refresh_token = data["refresh_token"]

    # 2. Login
    response = await client.post("/auth/login", json={
        "username": "testuser",
        "password": "strongpassword"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()

    # 3. Refresh Token
    response = await client.post("/auth/refresh", json={
        "refresh_token": refresh_token
    })
    assert response.status_code == 200
    new_data = response.json()
    assert "access_token" in new_data
    assert "refresh_token" in new_data
    assert new_data["refresh_token"] != refresh_token
    new_refresh_token = new_data["refresh_token"]

    # 4. Logout (Revoke)
    response = await client.post("/auth/logout", json={
        "refresh_token": new_refresh_token
    })
    assert response.status_code == 200

    # 5. Try Refresh with Revoked Token (Should Fail)
    response = await client.post("/auth/refresh", json={
        "refresh_token": new_refresh_token
    })
    assert response.status_code == 401
