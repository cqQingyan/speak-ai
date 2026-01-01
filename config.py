import os
import sys
from pydantic_settings import BaseSettings
from pydantic import Field
from loguru import logger

class Settings(BaseSettings):
    # Volcengine (ASR)
    VOLC_APPID: str = Field(default="", env="VOLC_APPID")
    VOLC_TOKEN: str = Field(default="", env="VOLC_TOKEN")
    VOLC_SECRET: str = Field(default="", env="VOLC_SECRET")

    # SiliconFlow (LLM)
    SILICON_KEY: str = Field(default="", env="SILICON_KEY")

    # Minimax (TTS)
    MINIMAX_GROUP_ID: str = Field(default="", env="MINIMAX_GROUP_ID")
    MINIMAX_API_KEY: str = Field(default="", env="MINIMAX_API_KEY")

    # App
    PORT: int = Field(default=8000, env="PORT")
    HOST: str = Field(default="0.0.0.0", env="HOST")
    ENV: str = Field(default="dev", env="ENV")

    # Database & Auth
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///./voice_assistant.db", env="DATABASE_URL")
    SECRET_KEY: str = Field(default="your-secret-key-change-me", env="SECRET_KEY")
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)

    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")

    # SSL
    SSL_CERT_FILE: str | None = Field(default=None, env="SSL_CERT_FILE")
    SSL_KEY_FILE: str | None = Field(default=None, env="SSL_KEY_FILE")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

def setup_logging():
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level> | {extra}",
        level="INFO"
    )
    # File logging (JSON formatted for "structure")
    logger.add(
        "app.log",
        rotation="500 MB",
        serialize=True,
        level="INFO"
    )

setup_logging()
