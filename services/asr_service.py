import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

SILICON_KEY = os.getenv("SILICON_KEY")

def transcribe_audio(audio_data):
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
        'file': ('audio.webm', audio_data, 'audio/webm'), # Assuming frontend sends webm
        'model': (None, 'TeleAI/TeleSpeech-ASR1.0'), # Or 'funasr/paraformer-v1' etc. Let's try TeleSpeech first.
    }

    headers = {
        "Authorization": f"Bearer {SILICON_KEY}"
    }

    try:
        # Note: 'model' is often a form field, not a file.
        response = requests.post(url, headers=headers, files=files)

        if response.status_code == 200:
            result = response.json()
            return result.get('text', '')
        else:
            print(f"ASR Error: {response.status_code} {response.text}")
            return None
    except Exception as e:
        print(f"ASR Exception: {e}")
        return None
