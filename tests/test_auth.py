import pytest
from auth import create_refresh_token, verify_refresh_token, revoke_refresh_token
from models import User, RefreshToken
from datetime import datetime, timedelta

@pytest.mark.asyncio
async def test_refresh_token_lifecycle(db_session):
    # Setup User
    user = User(username="testuser", email="test@test.com", hashed_password="hashed")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # 1. Create Token
    token = await create_refresh_token(db_session, user.id)
    assert token is not None

    # 2. Verify Token
    verified_user_id = await verify_refresh_token(db_session, token)
    assert verified_user_id == user.id

    # 3. Revoke Token
    await revoke_refresh_token(db_session, token)

    # 4. Verify Revoked Token (Should fail)
    verified_user_id = await verify_refresh_token(db_session, token)
    assert verified_user_id is None
