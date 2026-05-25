import base64
import uuid
import requests
import os
import logging
from typing import Optional
from dotenv import load_dotenv
from pathlib import Path

from config_ai import PROMPT_GIGACHAT, CONFIG, menu_user_message
from services.message_ai_parser import clean_recipe_output

BASE_DIR = Path(__file__).resolve().parent

# URL endpoints GigaChat API
OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
CHAT_COMPLETIONS_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"

# Кеш для токена (чтобы не запрашивать его каждый раз)
_cached_token: Optional[str] = None

load_dotenv()

auth_data = os.getenv("GIGACHAT_AUTH_KEY")

# Настройка логирования
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(name)s:%(message)s"
)

class GigaChatError(Exception):
    """Базовое исключение для ошибок GigaChat API."""
    pass


class GigaChatAuthError(GigaChatError):
    """Ошибка аутентификации в GigaChat API."""
    pass


class GigaChatAPIError(GigaChatError):
    """Ошибка при выполнении запроса к GigaChat API."""
    pass


def _get_authorization_header() -> str:
    """
    Формирует заголовок Authorization для Basic Auth.

    Returns:
        str: Base64-кодированная строка "CLIENT_ID:CLIENT_SECRET"
    """
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")


    if not client_id or not client_secret:
        raise GigaChatAuthError(
            "CLIENT_ID и CLIENT_SECRET должны быть установлены в переменных окружения "
            "(добавьте их в файл .env)"
        )

    # Кодируем credentials в base64
    credentials = f"{client_id}:{client_secret}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()

    return f"Basic {encoded_credentials}"

def get_access_token() -> str:
    """
    Получает OAuth токен для доступа к GigaChat API.

    Использует CLIENT_ID и CLIENT_SECRET из переменных окружения.
    Кеширует токен в памяти для повторного использования.

    Returns:
        str: Access token для использования в API запросах

    Raises:
        GigaChatAuthError: Если не удалось получить токен
    """
    global _cached_token

    # Используем кешированный токен, если он есть
    if _cached_token:
        logger.debug("Использование кешированного токена")
        return _cached_token

    logger.info("Получение access token из GigaChat API...")

    # Получаем заголовок Authorization
    try:
        auth_header = _get_authorization_header()
    except GigaChatAuthError:
        raise

    # Подготавливаем данные для запроса
    auth_data = {
        "scope": "GIGACHAT_API_PERS"
    }

    # Выполняем POST запрос для получения токена
    try:
        response = requests.post(
            OAUTH_URL,
            data=auth_data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": auth_header,
                "RqUID": str(uuid.uuid4()),
            },
            timeout=10,
            verify=False,  # TODO: включить SSL verify в проде
        )
        # Проверяем статус ответа
        if response.status_code != 200:
            error_msg = f"Ошибка аутентификации: статус {response.status_code}"
            try:
                error_detail = response.json()
                error_msg += f" - {error_detail}"
            except:
                error_msg += f" - {response.text}"
            logger.error(error_msg)
            raise GigaChatAuthError(error_msg)

        # Извлекаем токен из ответа
        token_data = response.json()
        access_token = token_data.get("access_token")

        if not access_token:
            error_msg = "Токен не найден в ответе API"
            logger.error(error_msg)
            raise GigaChatAuthError(error_msg)

        # Кешируем токен
        _cached_token = access_token
        logger.info("Access token успешно получен")

        return access_token

    except requests.exceptions.RequestException as e:
        error_msg = f"Ошибка сети при получении токена: {e}"
        logger.error(error_msg)
        raise GigaChatAuthError(error_msg) from e
    except Exception as e:
        if isinstance(e, GigaChatAuthError):
            raise
        error_msg = f"Неожиданная ошибка при получении токена: {e}"
        logger.error(error_msg)
        raise GigaChatAuthError(error_msg) from e

def download_image(image_url: str, path: str):
    r = requests.get(image_url)
    with open(path, "wb") as f:
        f.write(r.content)

def upload_gigachat_file(image_path: str, token: str) -> str | None:
    url = "https://gigachat.devices.sberbank.ru/api/v1/files"

    with open(image_path, "rb") as f:
        files = {
            "file": ("image.jpg", f, "image/jpeg"),
        }
        data = {
            "purpose": "general",
        }

        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            data=data,
            verify=False,
        )

    result = response.json()
    logger.debug("UPLOAD:", result)

    if response.status_code != 200:
        return None

    return result.get("id")


def call_gigachat_vision(image_path: str, token: str) -> str | None:
    file_id = upload_gigachat_file(image_path, token)

    if not file_id:
        return None

    payload = {
        "model": "GigaChat-Pro",
        "messages": [
            {
                "role": "user",
                "content": PROMPT_GIGACHAT,
                "attachments": [file_id],
            }
        ],
    }

    response = requests.post(
        "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        verify=False,
    )

    result = response.json()
    logger.debug("CHAT:", result)

    if response.status_code != 200:
        return None

    return result["choices"][0]["message"].get("content")

def call_gigachat_recipe(token: str, mode: str, user_prompt: str) -> str | None:
    system_content = CONFIG.get(mode)["system_prompt"]
    print(system_content)
    payload = {
        "model": "GigaChat-Pro",
        "messages": [
            {
                "role": "system",
                "content": system_content,
            },
            {
                "role": "user",
                "content": user_prompt,
            }
        ],
        "temperature": 0.3,
        "max_tokens": 400,
    }

    response = requests.post(
        "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        verify=False,
    )

    result = response.json()
    logger.debug("CHAT:", result)

    if response.status_code != 200:
        return None

    return result["choices"][0]["message"].get("content")

def generate_user_prompt_recipe(data: dict) -> str:
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


if __name__ == "__main__":
    data ={}

    access_token = get_access_token()

    data["recipe"] = "Хочу приготовить блюдо из курицы"
    data["persons"] = "на 6 человек"
    data["kcal"] = "на 1000 килокалорий"
    data["wishes"] = "Хочу средиземноморскую кухню на обед"
    user_message = generate_user_prompt_recipe(data)

    # image_url = "https://i.ibb.co/whzjRQ6Z/image.jpg"  # плов
    # image_url = "https://i.ibb.co/sJsXgjSh/download.jpg" ## борщ

    # image_path =  BASE_DIR / "picture/temp.jpg"
    #
    # download_image(image_url, image_path)
    #
    # content = call_gigachat_vision(image_path, access_token)
    mode = "menu"
    content = call_gigachat_recipe(access_token, mode =mode,user_prompt=menu_user_message)
    if mode == "recipe":
        result = clean_recipe_output(content)
    else:
        result = content
    logger.info(result)
