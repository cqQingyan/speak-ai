from sqlalchemy import Column, Integer, String, DateTime, LargeBinary, Text
from datetime import datetime, timezone
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True) # ForeignKey relation omitted for simplicity if not strictly needed, but good practice.
    role = Column(String) # 'user' or 'ai'
    content = Column(Text)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class TTSCache(Base):
    __tablename__ = "tts_cache"

    text_hash = Column(String, primary_key=True, index=True)
    audio_data = Column(LargeBinary)
    last_accessed = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    hit_count = Column(Integer, default=1)
