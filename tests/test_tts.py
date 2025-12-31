import pytest
import respx
import httpx
from services.tts_service import text_to_speech_stream

@pytest.mark.asyncio
async def test_tts_stream_success():
    async with respx.mock(base_url="https://api.minimaxi.com") as mock:
        # Mock SSE stream response
        # It's harder to mock streaming lines with respx easily without specific iterator support in mock,
        # but respx supports side_effect or iterator content.
        # Let's mock a simple JSON line for simplicity if possible.

        # Mocking 2 chunks
        chunk1 = 'data: {"data": {"audio": "0000"}}\n'
        chunk2 = 'data: {"data": {"audio": "1111"}}\n'

        # Need to return an iterator or stream-like object?
        # httpx.Response(200, content=...)
        # content can be an iterator of bytes.

        async def content_generator():
            yield chunk1.encode('utf-8')
            yield chunk2.encode('utf-8')

        mock.post(url__regex=r"/v1/t2a_v2.*").mock(return_value=httpx.Response(200, content=content_generator()))

        chunks = []
        async for chunk in text_to_speech_stream("Hello"):
            chunks.append(chunk)

        assert len(chunks) == 2
        assert chunks[0] == bytes.fromhex("0000")
        assert chunks[1] == bytes.fromhex("1111")
