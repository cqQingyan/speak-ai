import os
import logging
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Volcengine (ASR)
    VOLC_APPID = os.getenv("VOLC_APPID")
    VOLC_TOKEN = os.getenv("VOLC_TOKEN")
    VOLC_SECRET = os.getenv("VOLC_SECRET")

    # SiliconFlow (LLM)
    SILICON_KEY = os.getenv("SILICON_KEY")

    # Minimax (TTS)
    MINIMAX_GROUP_ID = os.getenv("MINIMAX_GROUP_ID")
    MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY")

    # App
    PORT = int(os.environ.get('PORT', 8000))
    HOST = os.environ.get('HOST', '0.0.0.0')

    # Database & Auth
    DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite+aiosqlite:///./voice_assistant.db')
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-change-me')
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
