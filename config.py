import os
import logging
from dotenv import load_dotenv

load_dotenv()

class Config:
    SILICON_KEY = os.getenv("SILICON_KEY")
    MINIMAX_GROUP_ID = os.getenv("MINIMAX_GROUP_ID")
    MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY")
    SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey") # Fallback for dev, should be set in env
    PORT = int(os.environ.get('PORT', 8000))
    HOST = os.environ.get('HOST', '0.0.0.0')

    # Defaults
    DEFAULT_VOICE_ID = "female-shaonv"
    DEFAULT_TEMPERATURE = 0.7

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
