import base64
import uuid
import requests
import os
import logging
from typing import Optional
from dotenv import load_dotenv
from pathlib import Path

from ai.local_model_vl import call_local_chat
from config_ai import (
    PROMPT_GIGACHAT,
    CONFIG,
    URL_AI,
    OAUTH_URL,
    generate_user_prompt_recipe,
    generate_user_prompt_menu,
    generate_user_prompt_repeat,
    generate_user_prompt_repeat_recipe_ingredientd,
    generate_user_prompt_repeat_recipe, generate_user_prompt_new_recipe,
)
from nutrition.nutrition_calc import (
    calculate_nutrition,
)
from services.message_ai_parser import (
    parse_ingredients_menu,
)
from services.message_builder import (
    scale_menu_weights,
    group_menu_by_meal,
    build_menu_text_from_parsed,
    normalize_piece_units,
    find_bad_items,
    replace_generic_products,
    merge_duplicate_items,
    merge_duplicate_recipe_items,
    normalize_taste_units,
    normalize_spoon_units,
    parse_recipe_blocks,
    build_recipe_text,
    normalize_ai_markdown,
    split_parentheses_products,
)
from services.recipe_utils import get_required_ingredients
from validators.recipe_validators import (
    validate_recipe,
    RecipeValidationResult)

BASE_DIR = Path(__file__).resolve().parent

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

models_ai_image = [
    "GigaChat-2-Pro",
    "GigaChat-2-Max",
    "GigaChat-Pro",
    "GigaChat-Max"
]

models_ai_chat = [
    "GigaChat"
]



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

def refresh_access_token() -> str:
    global _cached_token

    _cached_token = None
    return get_access_token()

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
        logger.error(
            "Upload error %s: %s",
            response.status_code,
            result,
        )
        return None

    return result.get("id")

def send_url_request(
    url: str,
    token: str,
    payload: dict,
) -> requests.Response | None:
    try:
        response = requests.post(
            url=url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
            verify=False,
            timeout=60,
        )
        return response

    except requests.RequestException as e:
        logger.error("GigaChat request network error: %s", e)
        return None

def send_gigachat_request(
        token: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
) -> requests.Response|None:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            }
        ],
        "temperature": 0,
        "max_tokens": 250,
    }

    response = send_url_request(url=URL_AI, token=token, payload=payload)

    return response


def call_gigachat_vision(image_path: str) -> str | None:
    token = get_access_token()
    file_id = upload_gigachat_file(image_path, token)

    if not file_id:
        logger.info("GigaChat upload failed. Refresh token and retry upload.")

        token = refresh_access_token()
        file_id = upload_gigachat_file(image_path, token)

        if not file_id:
            logger.debug("File_id: %s", file_id)
            return None

    last_response = None

    for model in models_ai_image:
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": PROMPT_GIGACHAT,
                    "attachments": [file_id],
                }
            ],
        }

        response = send_url_request(url=URL_AI, token=token, payload=payload)
        logger.info("Делаем запрос к model=%s", model)

        if response is None:
            continue

        last_response = response

        if response.status_code == 401:
            logger.info("GigaChat vision token expired. Refresh token and retry.")

            token = refresh_access_token()

            response = send_url_request(
                url=URL_AI,
                token=token,
                payload=payload,
            )

            if response is None:
                continue

            last_response = response

        if response.status_code == 200:
            result = response.json()
            logger.debug("CHAT: %s", result)
            return result["choices"][0]["message"].get("content")

    if last_response is not None:
        try:
            result = last_response.json()
        except ValueError:
            result = last_response.text

        logger.error(
            "GigaChat vision error %s: %s",
            last_response.status_code,
            result,
        )
    else:
        logger.error("GigaChat vision error: no response from all models")

    return None

def call_gigachat(token: str, mode: str, user_prompt: str) -> str | None:
    if os.getenv("FORCE_GIGACHAT_FAIL") == "1":
        logger.warning("DEBUG: GigaChat forced fail")
        return None

    cfg = CONFIG.get(mode, {})
    system_content = cfg.get("system_prompt", "")

    last_response = None

    for model in models_ai_chat:
        response = send_gigachat_request(
            token,
            model,
            system_content,
            user_prompt,
        )

        if response is None:
            continue

        last_response = response

        if response.status_code == 401:
            logger.info("GigaChat token expired. Refresh token and retry.")

            token = refresh_access_token()

            response = send_gigachat_request(
                token,
                model,
                system_content,
                user_prompt,
            )

            if response is None:
                continue

            last_response = response

        if response.status_code == 200:
            result = response.json()
            logger.debug("CHAT: %s", result)
            return result["choices"][0]["message"].get("content")

    if last_response is not None:
        try:
            result = last_response.json()
        except ValueError:
            result = last_response.text

        logger.error(
            "GigaChat error %s: %s",
            last_response.status_code,
            result,
        )
    else:
        logger.error("GigaChat error: no response from all models")

    return None

def call_chat_with_fallback(
    mode: str,
    user_prompt: str,
) -> str | None:

    token = get_access_token()

    if token:
        result = call_gigachat(
            token=token,
            mode=mode,
            user_prompt=user_prompt,
        )

        if result:
            print("AI SOURCE: GIGACHAT")
            return result

    system_prompt = CONFIG.get(mode, {}).get(
        "system_prompt",
        "",
    )

    print(f"AI SOURCE: LOCAL ({mode})")

    return call_local_chat(
        mode=mode,
        user_prompt=user_prompt,
        system_prompt=system_prompt,
    )


def process_recipe_ai_text(content: str, mode: str) -> tuple[str, RecipeValidationResult]:
    content = normalize_ai_markdown(content)
    content = normalize_piece_units(content)
    content = normalize_taste_units(content)
    content = normalize_spoon_units(content)

    parsed_recipe = parse_recipe_blocks(content)

    parsed_recipe["ingredients"] = split_parentheses_products(parsed_recipe["ingredients"])
    parsed_recipe["ingredients"] = replace_generic_products(parsed_recipe["ingredients"], mode)
    parsed_recipe["ingredients"] = merge_duplicate_recipe_items(parsed_recipe["ingredients"])

    recipe_text = build_recipe_text(parsed_recipe)
    validation = validate_recipe(recipe_text)

    return recipe_text, validation

def repair_recipe(
    mode: str,
    title: str,
    recipe_text: str,
    validation: RecipeValidationResult,
) -> str | None:
    has_ingredient_errors = any(
        "Неконкретный ингредиент:" in error
        or "Ингредиент содержит пояснение" in error
        for error in validation.errors
    )
    print(recipe_text)
    print(validation.errors)
    has_technology_errors = any(
        "Некорректная технология приготовления:" in error
        for error in validation.errors
    )

    has_required_ingredients_errors = any(
        "В рецепте отсутствует один из обязательных ингредиентов:" in error
        for error in validation.errors
    )

    parsed_recipe = parse_recipe_blocks(recipe_text)

    user_message = None

    if has_required_ingredients_errors:
        required_ingredients = get_required_ingredients(parsed_recipe["title"])

        user_message = generate_user_prompt_new_recipe(
            parsed_recipe,
            title,
            required_ingredients,
        )

    elif has_ingredient_errors:
        user_message = generate_user_prompt_repeat_recipe_ingredientd(
            parsed_recipe,
            validation.errors,
        )

    elif has_technology_errors:

        print("Parsed:", recipe_text)
        user_message = generate_user_prompt_repeat_recipe(
            recipe_text
        )

    if user_message is None:
        print("Не удалось определить тип ошибки для repair_recipe")
        return None

    print(user_message)

    content = call_chat_with_fallback(
        mode=mode,
        user_prompt=user_message,
    )

    if content is None:
        return None

    recipe_text, validation = process_recipe_ai_text(content, mode)

    if validation.is_valid:
        return recipe_text

    print("Ошибка после repair:\n", validation.errors)
    return None

def main():
    access_token = get_access_token()

    # Данные для user_prompt рецепта
    data = {}
    data["recipe"] = "Шурпа"
    data["persons"] = "на 4 человека"
    data["kcal"] = "на 1800 килокалорий"
    data["wishes"] = "Узбекская кухня"

    # Данные для user_prompt меню
    menu = {}
    kcal = 1993
    menu["meal_count"] = 3
    menu["wishes"] = "Нет"

    mode = "recipe"


    if mode == "recipe":

        user_message = generate_user_prompt_recipe(data=data)
        content = call_chat_with_fallback(
            mode=mode,
            user_prompt=user_message,
        )
        print(content)
        if content is None:
            return

        recipe_text, validation = process_recipe_ai_text(content, mode)

        if validation.is_valid:
            print(recipe_text)
            return recipe_text
        else:
            print("Ошибка:\n", validation.errors)
            parsed_recipe = parse_recipe_blocks(recipe_text)
            recipe_text = build_recipe_text(parsed_recipe)
            result = repair_recipe(mode, data["recipe"], recipe_text, validation)
            if result is None:
                print("ИИ не смог создать рецепт")
                print(result)
            else:
                print(result)


    if mode == "menu":

        user_message = generate_user_prompt_menu(menu, daily_kcal=kcal)

        content = call_chat_with_fallback(
            mode=mode,
            user_prompt=user_message,
        )
        print(content.strip())
        content = normalize_piece_units(content)
        parsed_menu = parse_ingredients_menu(content)
        print(parsed_menu)
        parsed_menu = replace_generic_products(parsed_menu, mode)
        parsed_menu = merge_duplicate_items(parsed_menu)
        print(parsed_menu)
        bad_items = find_bad_items(parsed_menu)
        if bad_items:
            print("Обобщённые продукты:", bad_items)
            print("Работаем над улучшением меню. Ждите...")


            user_message = generate_user_prompt_repeat(content=content, bad_words=bad_items)
            print(user_message)
            content = call_chat_with_fallback(
                mode=mode,
                user_prompt=user_message,
            )

            if not content:
                print("ИИ не вернул исправленное меню")


            print(content.strip())
            parsed_menu = parse_ingredients_menu(content)

        meals = group_menu_by_meal(parsed_menu)

        day_total_kcal = 0

        for meal_name, ingredients in meals.items():
            total, _ = calculate_nutrition(ingredients)
            day_total_kcal += total["kcal"]

        print(day_total_kcal)

        if day_total_kcal < 1993:
            scaled_menu = scale_menu_weights(
                parsed_menu=parsed_menu,
                target_kcal=1993,
                actual_kcal=day_total_kcal,
            )

            scaled_meals = group_menu_by_meal(scaled_menu)

            new_total = 0

            for meal_name, ingredients in scaled_meals.items():
                total, not_found = calculate_nutrition(ingredients)
                new_total += total["kcal"]

            print(new_total)
            print(build_menu_text_from_parsed(scaled_menu))
    if mode == "photo":
        # Данные для запроса определения по фотографии
        image_url = "https://i.ibb.co/whzjRQ6Z/image.jpg"  # плов
        # image_url = "https://i.ibb.co/sJsXgjSh/download.jpg" ## борщ

        image_path =  "D://AI//projects//ai-telegram-nutrition-bot//picture//uploads//plow.jpg"

        download_image(image_url, str(image_path))

        result = call_gigachat_vision(str(image_path), access_token)

        logger.info(result)


if __name__ == "__main__":

   main()