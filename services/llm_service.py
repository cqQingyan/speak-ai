import httpx
import logging
from config import Config
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10), retry=retry_if_exception_type(httpx.ConnectError))
async def chat_with_llm(user_text, history=[], temperature=None):
    """
    Sends text to SiliconFlow's DeepSeek-V3.2 model.
    """
    if temperature is None:
        temperature = Config.DEFAULT_TEMPERATURE

    url = "https://api.siliconflow.cn/v1/chat/completions"

    messages = history + [{"role": "user", "content": user_text}]

    payload = {
        "model": "deepseek-ai/DeepSeek-V3.2",
        "messages": messages,
        "stream": False,
        "max_tokens": 512,
        "temperature": temperature
    }

    headers = {
        "Authorization": f"Bearer {Config.SILICON_KEY}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)

        if response.status_code == 200:
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                return result['choices'][0]['message']['content']
            else:
                logger.error("LLM Error: No choices in response")
                return "抱歉，我没有理解您的意思。"
        else:
            logger.error(f"LLM Error: {response.status_code} {response.text}")
            return "服务暂时不可用，请稍后再试。"
    except Exception as e:
        logger.error(f"LLM Exception: {e}")
        raise # Allow retry
