import pytest
import respx
import httpx
from services.asr_service import transcribe_audio
from config import Config

@pytest.mark.asyncio
async def test_transcribe_audio_success():
    async with respx.mock(base_url="https://api.siliconflow.cn") as mock:
        mock.post("/v1/audio/transcriptions").mock(return_value=httpx.Response(200, json={"text": "Hello"}))

        result = await transcribe_audio(b"fake_audio")
        assert result == "Hello"

@pytest.mark.asyncio
async def test_transcribe_audio_failure():
    async with respx.mock(base_url="https://api.siliconflow.cn") as mock:
        mock.post("/v1/audio/transcriptions").mock(return_value=httpx.Response(500))

        result = await transcribe_audio(b"fake_audio")
        assert result is None
