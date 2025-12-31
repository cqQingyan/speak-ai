import httpx
import logging
import json
import base64
from config import Config
from sqlalchemy.future import select
from sqlalchemy import delete
from database import AsyncSessionLocal
from models import TTSCache
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

MAX_CACHE_SIZE = 100

async def get_cached_audio(text):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(TTSCache).where(TTSCache.text_hash == text))
        cache_entry = result.scalars().first()
        if cache_entry:
            # Update hit count and last accessed
            cache_entry.hit_count += 1
            cache_entry.last_accessed = datetime.utcnow() # Note: In models we used lambda default, here manual
            await session.commit()
            return cache_entry.audio_data
        return None

async def cache_audio(text, audio_data):
    async with AsyncSessionLocal() as session:
        # Check size
        # Simple count check
        count_res = await session.execute(select(func.count()).select_from(TTSCache))
        count = count_res.scalar()

        if count >= MAX_CACHE_SIZE:
             # Remove oldest
             subq = select(TTSCache.text_hash).order_by(TTSCache.last_accessed.asc()).limit(1)
             result = await session.execute(subq)
             oldest_hash = result.scalar()
             if oldest_hash:
                 await session.execute(delete(TTSCache).where(TTSCache.text_hash == oldest_hash))

        new_entry = TTSCache(text_hash=text, audio_data=audio_data)
        session.add(new_entry)
        await session.commit()

# Imports for DB function
from datetime import datetime
from sqlalchemy import func

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10), retry=retry_if_exception_type(httpx.ConnectError))
async def text_to_speech_stream(text, voice_id=None, speed=1.0):
    """
    Converts text to speech using Minimax T2A HTTP API with streaming.
    Yields chunks of audio bytes.
    """
    if not voice_id:
        voice_id = Config.DEFAULT_VOICE_ID

    # Check cache first
    cached_data = await get_cached_audio(text)
    if cached_data:
        logger.info("TTS Cache Hit")
        # Yield in chunks? Or one go. StreamingResponse supports bytes generator.
        # But our caller expects chunks to base64 encode.
        # Let's yield it in one chunk or simulate streaming.
        yield cached_data
        return

    url = f"https://api.minimaxi.com/v1/t2a_v2?groupId={Config.MINIMAX_GROUP_ID}"
    headers = {
        "Authorization": f"Bearer {Config.MINIMAX_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "speech-01-turbo",
        "text": text,
        "stream": True,
        "voice_setting": {
            "voice_id": voice_id,
            "speed": speed,
            "vol": 1.0,
            "pitch": 0
        },
        "audio_setting": {
            "sample_rate": 32000,
            "format": "mp3",
            "channel": 1
        }
    }

    full_audio = b""

    try:
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    logger.error(f"TTS Error: {response.status_code}")
                    return # Or raise for retry

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data:"):
                        line = line[5:]

                    try:
                        data = json.loads(line)
                        if 'data' in data and 'audio' in data['data']:
                            hex_audio = data['data']['audio']
                            chunk = bytes.fromhex(hex_audio)
                            full_audio += chunk
                            yield chunk
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        logger.error(f"TTS Stream Error: {e}")

        # Update Cache
        if full_audio:
            await cache_audio(text, full_audio)

    except Exception as e:
        logger.error(f"TTS Exception: {e}")
        raise # Allow retry
