import httpx
import logging
from config import Config

logger = logging.getLogger(__name__)

async def chat_with_llm(user_text, history=[]):
    """
    Sends text to SiliconFlow's DeepSeek-V3.2 model.

    Args:
        user_text (str): The user's input text.
        history (list): List of previous messages (optional).

    Returns:
        str: The AI's response text.
    """
    url = "https://api.siliconflow.cn/v1/chat/completions"

    messages = history + [{"role": "user", "content": user_text}]

    payload = {
        "model": "deepseek-ai/DeepSeek-V3.2",
        "messages": messages,
        "stream": False,
        "max_tokens": 512,
        "temperature": 0.7
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
        return "发生错误，请重试。"
