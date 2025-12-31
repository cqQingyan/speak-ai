import pytest
import respx
import httpx
from services.llm_service import chat_with_llm

@pytest.mark.asyncio
async def test_chat_with_llm_success():
    async with respx.mock(base_url="https://api.siliconflow.cn") as mock:
        mock.post("/v1/chat/completions").mock(return_value=httpx.Response(200, json={
            "choices": [{"message": {"content": "Hello User"}}]
        }))

        result = await chat_with_llm("Hi")
        assert result == "Hello User"

@pytest.mark.asyncio
async def test_chat_with_llm_failure():
    async with respx.mock(base_url="https://api.siliconflow.cn") as mock:
        mock.post("/v1/chat/completions").mock(return_value=httpx.Response(500))

        result = await chat_with_llm("Hi")
        assert result == "服务暂时不可用，请稍后再试。"
