import pytest
import io
from httpx import AsyncClient
import main
import services.asr_service
import services.llm_service
import services.tts_service

@pytest.mark.asyncio
async def test_process_audio_e2e(client: AsyncClient, monkeypatch):
    # Create a dummy audio file (wav header + silence)
    wav_header = b'RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00'
    dummy_audio = wav_header + b'\x00' * 100

    # Mock ASR
    async def mock_transcribe(*args, **kwargs):
        return "你好"

    # Patch BOTH source and destination to be safe
    monkeypatch.setattr(services.asr_service, "transcribe_audio", mock_transcribe)
    monkeypatch.setattr(main, "transcribe_audio", mock_transcribe)

    # Mock LLM
    async def mock_chat(*args, **kwargs):
        yield "你好"
        yield "！"

    monkeypatch.setattr(services.llm_service, "chat_with_llm", mock_chat)
    monkeypatch.setattr(main, "chat_with_llm", mock_chat)

    # Mock TTS
    async def mock_tts_stream(text_iterator):
        if hasattr(text_iterator, "__aiter__"):
                async for _ in text_iterator:
                    pass
        elif hasattr(text_iterator, "__iter__"):
                for _ in text_iterator:
                    pass
        yield b"audio_chunk"

    monkeypatch.setattr(services.tts_service, "text_to_speech_stream", mock_tts_stream)
    monkeypatch.setattr(main, "text_to_speech_stream", mock_tts_stream)

    # Mock Redis for Rate Limiting in Main App
    # Since rate limiter is in main.py logic (decorator), patching it is hard.
    # But we are using a separate redis instance for tests (in conftest? No, conftest uses in-memory DB but Redis URL is default localhost).
    # Ideally we should mock redis client.
    # But since we have a redis service in CI, it should work fine.

    # Send Request
    files = {
        "audio": ("test.wav", dummy_audio, "audio/wav")
    }

    async with client.stream("POST", "/api/process_audio", files=files) as response:
        assert response.status_code == 200

        # Read streaming response
        chunks = []
        async for line in response.aiter_lines():
            if line:
                chunks.append(line)

        assert len(chunks) > 0
        # Verify structure of NDJSON
        import json
        print(f"DEBUG CHUNK: {chunks[0]}")
        first_msg = json.loads(chunks[0])
        assert first_msg["type"] == "meta"
        assert first_msg["user_text"] == "你好"
