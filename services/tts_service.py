import httpx
import logging
import json
from config import Config
from functools import lru_cache

logger = logging.getLogger(__name__)

# Simple in-memory LRU cache using a dictionary for async context is tricky with decorators.
# We will use a global dictionary and manage size manually or use a library.
# Given constraints, a simple dict with max size logic is fine, or just standard lru_cache on a wrapper.
# Since we need to cache bytes (which are large), we should be careful.
# But for text keys it's fine.
# Let's use a simple global dict for now.
TTS_CACHE = {}
MAX_CACHE_SIZE = 100

async def text_to_speech_stream(text):
    """
    Converts text to speech using Minimax T2A HTTP API with streaming.
    Yields chunks of audio bytes.

    Args:
        text (str): Text to speak.

    Yields:
        bytes: Audio chunk.
    """
    # Check cache first
    if text in TTS_CACHE:
        logger.info("TTS Cache Hit")
        yield TTS_CACHE[text]
        return

    url = f"https://api.minimaxi.com/v1/t2a_v2?groupId={Config.MINIMAX_GROUP_ID}"
    headers = {
        "Authorization": f"Bearer {Config.MINIMAX_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "speech-01-turbo",
        "text": text,
        "stream": True, # Enable streaming
        "voice_setting": {
            "voice_id": "female-shaonv",
            "speed": 1.0,
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
                    return

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data:"): # SSE format
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
            if len(TTS_CACHE) >= MAX_CACHE_SIZE:
                # Remove oldest (randomish since py3.7+ dicts preserve insertion order, popitem(last=False) works for FIFO)
                # But standard dict popitem removes LIFO.
                # Let's just clear if full or remove arbitrary.
                TTS_CACHE.pop(next(iter(TTS_CACHE)))
            TTS_CACHE[text] = full_audio

    except Exception as e:
        logger.error(f"TTS Exception: {e}")
