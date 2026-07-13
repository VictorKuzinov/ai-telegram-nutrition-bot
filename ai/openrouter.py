import os
import requests

from dotenv import load_dotenv

from ai.local_model_vl import call_local_vision
from config_ai import PROMPT_GIGACHAT
from services.image_utils import image_to_data_url

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")


MODELS = [
    "nvidia/nemotron-nano-12b-v2-vl:free",
    "google/gemma-4-31b-it:free",
]

IMAGE_PATH = "D://AI//projects//ai-telegram-nutrition-bot//picture//uploads//olivier.jpg"




def send_openrouter_request(model: str, image_data_url: str) -> requests.Response:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": PROMPT_GIGACHAT,
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_data_url,
                        },
                    },
                ],
            }
        ],
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

    return response

def call_openrouter_vision(image_path: str) -> str | None:
    image_data_url = image_to_data_url(image_path)

    for model in MODELS:
        response = send_openrouter_request(model, image_data_url)

        print("Модель:", model)
        print("STATUS:", response.status_code)

        try:
            data = response.json()
        except ValueError:
            print("Ответ не JSON:")
            print(response.text)
            continue

        if "error" in data:
            print("ERROR:")
            print(data)

            message = data["error"].get("message", "")
            if message.startswith("Rate limit exceeded:"):
                return None

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
        return content

    return None

if __name__ == "__main__":

    ai_text = call_openrouter_vision(IMAGE_PATH)
    if ai_text is None:
        ai_text = call_local_vision(IMAGE_PATH)
    print(ai_text)