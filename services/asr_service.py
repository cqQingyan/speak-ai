import httpx
import logging
from config import Config
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10), retry=retry_if_exception_type(httpx.ConnectError))
async def transcribe_audio(audio_data):
    """
    Transcribes audio data using SiliconFlow's TeleSpeechASR.
    """
    url = "https://api.siliconflow.cn/v1/audio/transcriptions"

    # TeleSpeechASR usually expects a file upload.
    # We send the bytes directly as a file.
    files = {
        'file': ('audio.webm', audio_data, 'audio/webm'),
        'model': (None, 'TeleAI/TeleSpeech-ASR1.0'),
    }

    headers = {
        "Authorization": f"Bearer {Config.SILICON_KEY}"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, files=files)

        if response.status_code == 200:
            result = response.json()
            return result.get('text', '')
        else:
            logger.error(f"ASR Error: {response.status_code} {response.text}")
            return None # Or raise
    except Exception as e:
        logger.error(f"ASR Exception: {e}")
        raise # Allow retry
