import os
import base64
import mimetypes
import requests

from dotenv import load_dotenv

from config_ai import PROMPT_GIGACHAT

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")


MODELS = [
    "moonshotai/kimi-k2.6:free",
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-nano-12b-v2-vl:free",
    "qwen/qwen2.5-vl-7b-instruct:free",
    "google/gemma-3-27b-it:free",
    "openrouter/free",
]
IMAGE_PATH = "C:\\PyProject\\nutriciolog_bot\\picture\\uploads\\Плов.jpg"


def image_to_data_url(path: str) -> str:
    mime_type, _ = mimetypes.guess_type(path)
    if mime_type is None:
        mime_type = "image/jpeg"

    with open(path, "rb") as file:
        encoded = base64.b64encode(file.read()).decode("utf-8")

    return f"data:{mime_type};base64,{encoded}"


image_data_url = image_to_data_url(IMAGE_PATH)

for model in MODELS:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": PROMPT_GIGACHAT
                    }
                ]
            }
        ]
    }

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )

    print("Модель:", model)
    print("STATUS:", response.status_code)

    try:
        data = response.json()
    except ValueError:
        print("Ответ не JSON:")
        print(response.text)
        continue

    if response.status_code != 200:
        print("ERROR:")
        print(data)
        continue

    if "choices" not in data:
        print("Ответ без choices:")
        print(data)
        continue

    content = data["choices"][0]["message"]["content"]
    print(content)
    break