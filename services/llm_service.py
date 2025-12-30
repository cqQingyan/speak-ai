import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

SILICON_KEY = os.getenv("SILICON_KEY")

def chat_with_llm(user_text, history=[]):
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
        "model": "deepseek-ai/DeepSeek-V3.2", # Confirmed in test_apis.py
        "messages": messages,
        "stream": False, # Non-streaming for simpler initial implementation, or use stream if we want faster TTFB later.
        "max_tokens": 512,
        "temperature": 0.7
    }

    headers = {
        "Authorization": f"Bearer {SILICON_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, headers=headers, json=payload)

        if response.status_code == 200:
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                return result['choices'][0]['message']['content']
            else:
                print("LLM Error: No choices in response")
                return "抱歉，我没有理解您的意思。"
        else:
            print(f"LLM Error: {response.status_code} {response.text}")
            return "服务暂时不可用，请稍后再试。"
    except Exception as e:
        print(f"LLM Exception: {e}")
        return "发生错误，请重试。"
