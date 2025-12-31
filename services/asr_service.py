import httpx
import logging
from config import Config

logger = logging.getLogger(__name__)

async def transcribe_audio(audio_data):
    """
    Transcribes audio data using SiliconFlow's TeleSpeechASR.

    Args:
        audio_data (bytes): The audio file content (e.g., mp3 or wav bytes).

    Returns:
        str: The transcribed text, or None if failed.
    """
    url = "https://api.siliconflow.cn/v1/audio/transcriptions"

    # TeleSpeechASR usually expects a file upload.
    # Based on standard OpenAI-compatible ASR endpoints:
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
            return None
    except Exception as e:
        logger.error(f"ASR Exception: {e}")
        return None
