from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from config import settings
from models import RefreshToken
import secrets
from loguru import logger

# Use Argon2
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

async def create_refresh_token(db: AsyncSession, user_id: int) -> str:
    token = secrets.token_urlsafe(64)
    expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    db_token = RefreshToken(
        user_id=user_id,
        token=token,
        expires_at=expires_at
    )
    db.add(db_token)
    await db.commit()
    return token

async def verify_refresh_token(db: AsyncSession, token: str) -> Optional[int]:
    result = await db.execute(select(RefreshToken).where(RefreshToken.token == token))
    db_token = result.scalars().first()

    if not db_token:
        return None

    if db_token.revoked:
        logger.warning(f"Attempted use of revoked token: {token}")
        return None

    if db_token.expires_at < datetime.utcnow():
        return None

    return db_token.user_id

async def revoke_refresh_token(db: AsyncSession, token: str):
    result = await db.execute(select(RefreshToken).where(RefreshToken.token == token))
    db_token = result.scalars().first()
    if db_token:
        db_token.revoked = True
        await db.commit()

def verify_token(token: str):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return username
    except JWTError:
        return None
