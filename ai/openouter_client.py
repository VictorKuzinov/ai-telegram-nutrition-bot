import os
from pathlib import Path
from typing import Any
import requests

from dotenv import load_dotenv

from config_ai import (
    CONFIG,
    choice_menu,
    reserve_model,
)
from ai.gigachat import (
    call_gigachat_vision,
    download_image,
    get_access_token,
)
from nutrition.nutrition_cache import (
    save_or_increment_cache,
    cache_path,
)
from nutrition.nutrition_calc import (
    calculate_nutrition,
    footer_recipe,
)
from services.message_ai_parser import parse_ingredients
from services.message_builder import (
    filter_user_message,
    clean_vision_output,
)

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")
INDEX: dict[str, dict[str, Any]] = {}
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

def call_api(
    model: str,
    prompt: str,
    user_message: str,
    temperature: float,
    max_tokens: int,
) -> dict[str, Any]:
    """
    Отправляет текстовый запрос в OpenRouter Chat Completions API.

    Используется для режимов recipe, menu и chat.
    Возвращает полный JSON-ответ API.
    """
    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": prompt,
            },
            {
                "role": "user",
                "content": user_message,
            },
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    return response.json()


def is_invalid_response(mode: str, data: dict[str, Any]) -> bool:
    """
    Валидирует ответ модели для дальнейшей обработки.

    Общие признаки плохого ответа:
    - ответ обрезан по длине;
    - content пустой или отсутствует.

    Для режима menu дополнительно проверяет наличие обязательных пунктов меню.
    """
    content = data["choices"][0]["message"]["content"]
    base_invalid = False
    mode_invalid = False

    if (
        data["choices"][0]["finish_reason"] == "length"
        or content is None
        or content.strip() == ""
    ):
        base_invalid = True

    if mode == "menu" and content is not None:
        mode_invalid = not all(item in content for item in choice_menu)

    return base_invalid or mode_invalid


def send_request(
    mode: str,
    model: str,
    prompt: str,
    user_message: str,
    temperature: float,
    max_tokens: int,
) -> str:
    """
    Отправляет запрос основной модели и при плохом ответе пробует резервную модель.

    Возвращает текст ответа модели или сообщение об ошибке.
    """
    data = call_api(model, prompt, user_message, temperature, max_tokens)
    content = data["choices"][0]["message"]["content"]

    if is_invalid_response(mode, data):
        data = call_api(reserve_model, prompt, user_message, temperature, max_tokens)
        content = data["choices"][0]["message"]["content"]

    if is_invalid_response(mode, data):
        return "Ошибка получения ответа от резервной модели"

    return content

def ask_ai(user_message: str, mode: str = "chat") -> str:
    """
    Получает настройки режима из CONFIG и отправляет запрос в текстовую модель.

    При ошибке основной модели пробует fallback-маршрут openrouter/free.
    """
    cfg = CONFIG.get(mode, {})
    model = cfg.get("model", "openrouter/free")
    temperature = cfg.get("temperature", 0.5)
    prompt = cfg.get("system_prompt", "")
    max_tokens = cfg.get("max_tokens", 300)

    try:
        return send_request(mode, model, prompt, user_message, temperature, max_tokens)
    except Exception as e:
        print("Основная модель недоступна, пробую fallback:", e)

    try:
        return send_request(
            mode,
            "openrouter/free",
            prompt,
            user_message,
            temperature,
            max_tokens,
        )
    except Exception as fallback_error:
        return f"Ошибка: {str(fallback_error)}"

def handle_recipe_mode(ai_text: str) -> str:
    """
    Обрабатывает ответ модели в режиме recipe.

    Парсит ингредиенты, рассчитывает БЖУ и добавляет итоговый блок к рецепту.
    """
    if ai_text.startswith("Ошибка"):
        return "Ошибка получения данных от ИИ"

    answer = ai_text.strip()
    parsed = parse_ingredients(answer)

    total, not_found = calculate_nutrition(parsed)
    answer += "\n" + footer_recipe(total)

    if not_found:
        answer += "\n⚠ Не учтены в расчёте:\n"
        for item in not_found:
            answer += f"- {item}\n"

    save_or_increment_cache(cache_path, not_found)

    return answer


def handle_menu_mode(ai_text: str) -> str:
    """
    Обрабатывает ответ модели в режиме menu.

    Сейчас возвращает текст без дополнительной обработки.
    """
    return ai_text


def handle_chat_mode(ai_text: str) -> str:
    """
    Обрабатывает ответ модели в режиме chat.
    """
    if ai_text.startswith("Ошибка"):
        return "Ошибка получения ответа от ИИ"

    return ai_text


def handle_photo_mode(image_url: str) -> str:
    """
    Обрабатывает фото еды.

    Скачивает изображение, отправляет его в GigaChat,
    получает предполагаемое блюдо/продукты,
    парсит ответ и рассчитывает пищевую ценность.

    Временный режим: расчёт выполняется сразу.
    Позже лучше заменить на подтверждение пользователем через Telegram-кнопки.
    """
    access_token = get_access_token()
    image_path = BASE_DIR / "picture/temp.jpg"

    download_image(image_url, str(image_path))
    content = call_gigachat_vision(str(image_path), access_token)

    if not content:
        return "Не удалось распознать изображение."

    cleaned = clean_vision_output(content)

    if not cleaned.strip():
        return "Не удалось извлечь ингредиенты с фото."

    parsed = parse_ingredients(cleaned)

    if not parsed:
        return "Не удалось разобрать ингредиенты."

    total, not_found = calculate_nutrition(parsed)

    answer = "Распознано по фото:\n"
    answer += cleaned
    answer += "\n"
    answer += footer_recipe(total)

    if not_found:
        answer += "\n⚠ Не учтены в расчёте:\n"
        for item in not_found:
            answer += f"- {item}\n"

    save_or_increment_cache(cache_path, not_found)

    answer += "\n⚠ Оценка приблизительная (по фото)"

    return answer


def generate_user_prompt(data: dict) -> str:
    user_prompt = f"""
        Ты нутрициолог и повар.

        Составь рецепт блюда.

        Основной запрос:
        {data["recipe"]}

        Количество человек:
        {data["persons"]}

        Ограничение по калориям:
        {data["kcal"]}

        Дополнительные пожелания:
        {data["wishes"]}

        Требования:
        - краткий формат;
        - список ингредиентов;
        - пошаговое приготовление;
        - примерная калорийность;
        - без длинных вступлений.
    """
    return user_prompt

def main() -> None:
    """
    Точка входа для локальной отладки режимов приложения.

    В Telegram-боте вместо этой функции будут использоваться обработчики сообщений.
    """
    mode = "recipe"
    data={}

    if mode == "recipe":
        data["recipe"] = "Хочу приготовить блюдо из курицы"
        data["persons"] = "на 6 человек"
        data["kcal"] = "на 1000 килокалорий"
        data["wishes"] = "Хочу средиземноморскую кухню на обед"
        user_message = generate_user_prompt(data)
        print(user_message)
        ai_text = ask_ai(user_message=user_message, mode=mode)
        print(ai_text)
        result_text = handle_recipe_mode(ai_text)

    elif mode == "menu":
        user_message = "Составь меню на 1993 ккал, на один день."
        ai_text = ask_ai(user_message=user_message, mode=mode)
        result_text = handle_menu_mode(ai_text)

    elif mode == "chat":
        user_message = "..."  # Потом будет из Telegram.
        allowed, filter_answer = filter_user_message(user_message)

        if not allowed:
            result_text = filter_answer
        else:
            ai_text = ask_ai(user_message=user_message, mode=mode)
            result_text = handle_chat_mode(ai_text)

    elif mode == "photo":
        # image_url = "https://..."  # Потом будет из Telegram.
        image_url = "https://i.ibb.co/whzjRQ6Z/image.jpg"  # плов
        # image_url = "https://i.ibb.co/sJsXgjSh/download.jpg"  # борщ
        result_text = handle_photo_mode(image_url)

    else:
        result_text = "Неизвестный режим"

    print(result_text)


if __name__ == "__main__":
    main()
