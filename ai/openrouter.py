import os
import base64
import mimetypes
import requests

from dotenv import load_dotenv

from config_ai import PROMPT_GIGACHAT

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")


MODELS = [
    "nvidia/nemotron-nano-12b-v2-vl:free",
    "google/gemma-4-31b-it:free",
]

IMAGE_PATH = "C:\\PyProject\\nutriciolog_bot\\picture\\uploads\\Плов.jpg"


def image_to_data_url(path: str) -> str:
    mime_type, _ = mimetypes.guess_type(path)
    if mime_type is None:
        mime_type = "image/jpeg"

    with open(path, "rb") as file:
        encoded = base64.b64encode(file.read()).decode("utf-8")

    return f"data:{mime_type};base64,{encoded}"

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
        print(content)
        return content

    return None

if __name__ == "__main__":

    ai_text = call_openrouter_vision(IMAGE_PATH)
    print(ai_text)