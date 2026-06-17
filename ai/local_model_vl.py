import requests

from config_ai import PROMPT_GIGACHAT
from services.image_utils import image_to_data_url

LOCAL_URL = "http://127.0.0.1:8000/v1/chat/completions"
LOCAL_MODEL = "qwen2.5-vl-local"


def send_local_request(image_data_url: str) -> requests.Response:
    payload = {
        "model": LOCAL_MODEL,
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
        "temperature": 0,
        "max_tokens": 300,
    }

    return requests.post(
        LOCAL_URL,
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=120,
    )


def call_local_vision(image_path: str) -> str | None:
    image_data_url = image_to_data_url(image_path)

    try:
        response = send_local_request(image_data_url)
    except requests.RequestException as exc:
        print("LOCAL ERROR:", exc)
        return None

    print("LOCAL STATUS:", response.status_code)

    try:
        data = response.json()
    except ValueError:
        print("LOCAL ответ не JSON:")
        print(response.text)
        return None

    if response.status_code != 200:
        print("LOCAL ERROR:")
        print(data)
        return None

    if "choices" not in data:
        print("LOCAL ответ без choices:")
        print(data)
        return None

    content = data["choices"][0]["message"]["content"]
    print("LOCAL CONTENT:")
    print(content)

    return content