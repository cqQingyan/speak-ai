import httpx
import logging
import json
import hashlib
from redis.asyncio import Redis
from tenacity import retry, stop_after_attempt, wait_exponential
from config import settings

logger = logging.getLogger(__name__)

# Redis Connection
redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)

# Shared Client
async def get_httpx_client():
    limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)
    return httpx.AsyncClient(limits=limits, timeout=30.0)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
async def chat_with_llm(user_text, history=[]):
    """
    Sends text to SiliconFlow's DeepSeek-V3.2 model and yields tokens.

    Args:
        user_text (str): The user's input text.
        history (list): List of previous messages.

    Yields:
        str: Text tokens.
    """
    # Cache Key Generation
    # We cache based on full history + current text
    # Ensure sort_keys=True for deterministic JSON string
    cache_key = f"llm:{hashlib.md5(json.dumps(history + [{'role': 'user', 'content': user_text}], sort_keys=True).encode()).hexdigest()}"

    # Check Cache
    cached_response = await redis_client.get(cache_key)
    if cached_response:
        logger.info("LLM Cache Hit")
        # Yield cached tokens (simulated stream)
        for token in json.loads(cached_response):
            yield token
        return

    url = "https://api.siliconflow.cn/v1/chat/completions"

    messages = history + [{"role": "user", "content": user_text}]

    payload = {
        "model": "deepseek-ai/DeepSeek-V3.2",
        "messages": messages,
        "stream": True, # Enabled Streaming
        "max_tokens": 512,
        "temperature": 0.7
    }

    headers = {
        "Authorization": f"Bearer {settings.SILICON_KEY}",
        "Content-Type": "application/json"
    }

    full_response_tokens = []

    try:
        client = await get_httpx_client()
        async with client.stream("POST", url, headers=headers, json=payload) as response:
            if response.status_code != 200:
                logger.error(f"LLM Error: {response.status_code}")
                yield "抱歉，服务暂时不可用。"
                return

            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    line = line[5:].strip()
                    if line == "[DONE]":
                        break
                    try:
                        data = json.loads(line)
                        if 'choices' in data and len(data['choices']) > 0:
                            delta = data['choices'][0].get('delta', {})
                            if 'content' in delta:
                                token = delta['content']
                                full_response_tokens.append(token)
                                yield token
                    except json.JSONDecodeError:
                        continue

        # Set Cache (Expire in 1 hour)
        if full_response_tokens:
            await redis_client.setex(cache_key, 3600, json.dumps(full_response_tokens))

    except Exception as e:
        logger.error(f"LLM Exception: {e}")
        yield "发生错误。"
        raise e # Re-raise for retry
