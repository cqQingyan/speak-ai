import httpx
import logging
import json
import hashlib
from redis.asyncio import Redis
from tenacity import retry, stop_after_attempt, wait_exponential
from config import settings

logger = logging.getLogger(__name__)

# Redis for Audio Caching (Binary safe)
redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=False)

# Shared Client
async def get_httpx_client():
    limits = httpx.Limits(max_keepalive_connections=20, max_connections=50)
    return httpx.AsyncClient(limits=limits, timeout=10.0)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=5)
)
async def tts_request(text):
    """
    Helper to send a single TTS request for a sentence.
    Yields the full audio bytes for that sentence once complete.
    """
    if not text.strip():
        return

    # Cache Key
    cache_key = f"tts:{hashlib.md5(text.encode()).hexdigest()}"

    # Check Cache
    cached_audio = await redis_client.get(cache_key)
    if cached_audio:
        logger.info("TTS Cache Hit")
        yield cached_audio
        return

    url = f"https://api.minimaxi.com/v1/t2a_v2?groupId={settings.MINIMAX_GROUP_ID}"
    headers = {
        "Authorization": f"Bearer {settings.MINIMAX_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "speech-01-turbo",
        "text": text,
        "stream": True,
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
        client = await get_httpx_client()
        async with client.stream("POST", url, headers=headers, json=payload) as response:
            if response.status_code != 200:
                logger.error(f"TTS Error: {response.status_code}")
                # Don't retry on 4xx errors usually, but 5xx yes.
                # raising error triggers tenacity retry
                if response.status_code >= 500:
                    response.raise_for_status()
                return

            async for line in response.aiter_lines():
                if not line: continue
                if line.startswith("data:"):
                    line = line[5:]

                try:
                    data = json.loads(line)
                    if 'data' in data and 'audio' in data['data']:
                        chunk = bytes.fromhex(data['data']['audio'])
                        full_audio += chunk
                except json.JSONDecodeError:
                    continue

        # Cache Update (Expire in 24 hours)
        if full_audio:
             await redis_client.setex(cache_key, 86400, full_audio)
             yield full_audio

    except Exception as e:
        logger.error(f"TTS Request Exception: {e}")
        raise e

async def text_to_speech_stream(text_iterator):
    """
    Consumes an async generator of text tokens, buffers them into sentences,
    and yields audio chunks (full sentences) for each sentence.
    """
    buffer = ""
    punctuation = "。！？；!?;."

    async for token in text_iterator:
        buffer += token

        # Check if we have a full sentence
        if any(p in token for p in punctuation):
            if buffer[-1] in punctuation or len(buffer) > 50:
                try:
                    async for audio_chunk in tts_request(buffer):
                        yield audio_chunk
                except Exception:
                    pass # Continue to next sentence even if one fails
                buffer = ""

    # Process remaining buffer
    if buffer:
        try:
            async for audio_chunk in tts_request(buffer):
                yield audio_chunk
        except Exception:
            pass
