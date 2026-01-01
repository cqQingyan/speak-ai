import httpx
import logging
import json
import asyncio
from config import Config

logger = logging.getLogger(__name__)

# Cache (Simple Dict for now)
TTS_CACHE = {}
MAX_CACHE_SIZE = 100

async def tts_request(text):
    """
    Helper to send a single TTS request for a sentence.
    Yields the full audio bytes for that sentence once complete.
    """
    if not text.strip():
        return

    # Check Cache
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
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    logger.error(f"TTS Error: {response.status_code}")
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

        # Cache Update and Yield Full Buffer
        # We yield the complete buffer so the frontend gets a valid playable file (MP3) for this sentence.
        if full_audio:
            if len(TTS_CACHE) >= MAX_CACHE_SIZE:
                TTS_CACHE.pop(next(iter(TTS_CACHE)))
            TTS_CACHE[text] = full_audio
            yield full_audio

    except Exception as e:
        logger.error(f"TTS Request Exception: {e}")

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
            # Actually, let's just send the buffer if it ends with punctuation or is long enough
            # to ensure we don't send too small fragments that sound unnatural.
            if buffer[-1] in punctuation or len(buffer) > 50:
                async for audio_chunk in tts_request(buffer):
                    yield audio_chunk
                buffer = ""

    # Process remaining buffer
    if buffer:
        async for audio_chunk in tts_request(buffer):
            yield audio_chunk
