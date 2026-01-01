import httpx
import logging
from config import Config

logger = logging.getLogger(__name__)

async def chat_with_llm(user_text, history=[]):
    """
    Sends text to SiliconFlow's DeepSeek-V3.2 model and yields tokens.

    Args:
        user_text (str): The user's input text.
        history (list): List of previous messages.

    Yields:
        str: Text tokens.
    """
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
        "Authorization": f"Bearer {Config.SILICON_KEY}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient() as client:
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
                                    yield delta['content']
                        except json.JSONDecodeError:
                            continue
    except Exception as e:
        logger.error(f"LLM Exception: {e}")
        yield "发生错误。"

# Needed for json module above
import json
