import numpy as np
import io
import logging
from scipy.io import wavfile
from scipy import signal

logger = logging.getLogger(__name__)

def process_audio_data(audio_bytes: bytes) -> bytes:
    """
    Applies basic audio processing to improve ASR accuracy.
    Note: ASR typically works best with raw or slightly processed audio.
    Severe filtering can harm accuracy if not tuned.

    Here we apply:
    1. Check if it's WAV (based on header) - if not, return as is (since we can't decode mp3/webm without ffmpeg easily in pure python without extra libs).
    2. If WAV, apply high-pass filter to remove rumble < 80Hz.
    3. Normalize volume.
    """

    # Simple check for WAV header (RIFF....WAVE)
    if not audio_bytes.startswith(b'RIFF'):
        # Not a wav file (likely webm from browser), return as is.
        # Without ffmpeg, we can't easily convert/process webm.
        return audio_bytes

    try:
        # Load data
        fs, data = wavfile.read(io.BytesIO(audio_bytes))

        # Ensure float for processing
        data_float = data.astype(np.float32)

        # 1. High-pass filter (80Hz) to remove DC offset and rumble
        sos = signal.butter(4, 80, 'hp', fs=fs, output='sos')
        filtered = signal.sosfilt(sos, data_float)

        # 2. Normalize (Max amplitude to 0.95)
        max_val = np.max(np.abs(filtered))
        if max_val > 0:
            filtered = filtered / max_val * 0.95

        # Convert back to int16
        if data.dtype == np.int16:
            final_data = (filtered * 32767).astype(np.int16)
        else:
             final_data = filtered.astype(data.dtype)

        # Write to bytes
        out_buf = io.BytesIO()
        wavfile.write(out_buf, fs, final_data)
        return out_buf.getvalue()

    except Exception as e:
        logger.error(f"Audio Processing Failed: {e}")
        return audio_bytes
