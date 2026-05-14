import json
import os
import re
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from config_ai import CONFIG, choice_menu, reserve_model
from gigachat_photo import call_gigachat_vision, download_image, get_access_token


SPECIAL_FORMS: dict[str, str] = {
    "огурцы": "огурец",
    "помидоры": "помидор",
    "томаты": "томат",
    "оливки": "оливка",
    "маслины": "маслина",
    "яйца": "яйцо",
    "перцы": "перец",
    "яблоки": "яблоко",
    "бананы": "банан",
    "апельсины": "апельсин",
    "лимоны": "лимон",
    "грибы": "гриб",
    "шампиньоны": "шампиньон",
    "картофелины": "картофель",
    "картошки": "картофель",
    "моркови": "морковь",
    "морковки": "морковь",
    "свеклы": "свекла",
    "чеснока": "чеснок",
}

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")
INDEX: dict[str, dict[str, Any]] = {}
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
cache_path = DATA_DIR / "missing_ingredients.json"

NutritionTotal = dict[str, float]
ParsedIngredients = list[tuple[str, float]]
IngredientRecord = dict[str, Any]


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
    Проверяет, пригоден ли ответ модели для дальнейшей обработки.

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


def filter_user_message(text: str) -> tuple[bool, str]:
    """
    Выполняет базовую фильтрацию пользовательского сообщения.

    Отсекает пустые, слишком короткие, бессмысленные сообщения
    и простые попытки prompt injection.

    Возвращает:
    - True и пустую строку, если сообщение допустимо;
    - False и текст ответа пользователю, если сообщение нужно отклонить.
    """
    text_lower = text.lower().strip()

    if not text_lower or len(text_lower) < 3:
        return False, "Пожалуйста, задайте вопрос по питанию."

    if len(set(text_lower)) < 3:
        return False, "Пожалуйста, задайте вопрос по питанию."

    suspicious_phrases = [
        "игнорируй инструкции",
        "забудь инструкции",
        "ты теперь",
        "system prompt",
        "act as",
        "ignore previous",
    ]

    if any(phrase in text_lower for phrase in suspicious_phrases):
        return False, "Я отвечаю только на вопросы по питанию."

    return True, ""


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


def build_index(data: list[IngredientRecord]) -> dict[str, IngredientRecord]:
    """
    Строит индекс ингредиентов для быстрого поиска.

    В индекс добавляются:
    - id;
    - русское название;
    - английское название;
    - русские алиасы;
    - английские алиасы.
    """
    index: dict[str, IngredientRecord] = {}

    for item in data:
        index[item["id"].lower()] = item
        index[item["name_ru"].lower()] = item

        if item.get("name_en"):
            index[item["name_en"].lower()] = item

        for alias in item.get("aliases_ru", []):
            index[alias.lower()] = item

        for alias in item.get("aliases_en", []):
            if alias:
                index[alias.lower()] = item

    return index


def load_ingredients_index(data_path: Path) -> dict[str, IngredientRecord]:
    """
    Загружает базу ингредиентов из JSON-файла и возвращает поисковый индекс.
    """
    with open(data_path, encoding="utf-8") as f:
        ingredients: list[IngredientRecord] = json.load(f)

    return build_index(ingredients)


def normalize_name(name: str) -> str:
    """
    Нормализует название продукта для поиска в базе.

    Убирает дефисы, скобки, служебные слова
    и приводит некоторые формы множественного числа к базовой форме.
    """
    garbage_patterns = [
        r"\(.*?\)",  # всё в скобках
        r"\bбез [а-яё]+\b",  # без кожи / без костей
        r"\bсвеж[а-яё]*\b",
        r"\bзамороженн[а-яё]*\b",
        r"\bохлажденн[а-яё]*\b",
        r"\bжарен[а-яё]*\b",
        r"\bотварн[а-яё]*\b",
        r"\bзапеченн[а-яё]*\b",
        r"\bмолот[а-яё]*\b",
    ]

    name = name.lower()
    name = name.lstrip("- ").strip()
    name = re.sub(r"\(.*?\)", "", name)

    for pattern in garbage_patterns:
        name = re.sub(pattern, "", name)
        name = name.strip()

    name = re.sub(r"\s+", " ", name)
    name = SPECIAL_FORMS.get(name, name)

    return name.strip()


def find_ingredient(name: str) -> IngredientRecord | None:
    """
    Ищет ингредиент в индексе базы.

    Сначала ищет полное нормализованное имя.
    Если не найдено — пробует искать по отдельным словам с конца строки.
    """
    if not name:
        return None

    normalized_name = normalize_name(name)
    found = INDEX.get(normalized_name.lower())

    if found:
        return found

    words = normalized_name.split()
    for word in reversed(words):
        found = INDEX.get(word.lower())
        if found:
            return found

    return None


def parse_ingredients(text: str) -> ParsedIngredients:
    """
    Извлекает из текста список продуктов и их вес.

    Поддерживает строки вида:
    - продукт — 100 г
    - продукт - 100 гр
    - продукт — 100 мл

    Единицы "шт" игнорируются, потому что пока нет пересчёта штук в граммы.
    """
    parsed: ParsedIngredients = []

    for line in text.splitlines():
        match = re.search(
            r"(.+?)\s*[—-]\s*(\d+(?:[.,]\d+)?)\s*(г|гр|мл|шт)",
            line.lower(),
        )

        if not match:
            continue

        name = match.group(1).strip()
        name = name.lstrip("- ").strip()
        unit = match.group(3).strip()
        amount = float(match.group(2).replace(",", "."))

        if unit not in ("г", "гр", "мл"):
            continue

        parsed.append((name, amount))

    return parsed


def calculate_nutrition(parsed_ingredients: ParsedIngredients) -> tuple[NutritionTotal, list[str]]:
    """
    Рассчитывает калорийность, БЖУ и вес блюда.

    Возвращает:
    - словарь с итогами на весь рецепт и на 100 г;
    - список ингредиентов, которых нет в базе.
    """
    not_found: list[str] = []
    total_kcal = 0.0
    total_protein = 0.0
    total_fat = 0.0
    total_carbs = 0.0
    total_weight = 0.0

    for name, grams in parsed_ingredients:
        item = find_ingredient(name)

        if item:
            coef = grams / 100
            total_kcal += item["kcal_per_100g"] * coef
            total_protein += item["protein_per_100g"] * coef
            total_fat += item["fat_per_100g"] * coef
            total_carbs += item["carbs_per_100g"] * coef
            total_weight += grams
        else:
            not_found.append(name)

    if total_weight > 0:
        kcal_100 = total_kcal / total_weight * 100
        protein_100 = total_protein / total_weight * 100
        fat_100 = total_fat / total_weight * 100
        carbs_100 = total_carbs / total_weight * 100
    else:
        kcal_100 = protein_100 = fat_100 = carbs_100 = 0.0

    total: NutritionTotal = {
        "kcal": round(total_kcal, 0),
        "protein": round(total_protein, 1),
        "fat": round(total_fat, 1),
        "carbs": round(total_carbs, 1),
        "weight": round(total_weight, 1),
        "kcal_100g": round(kcal_100, 0),
        "protein_100g": round(protein_100, 1),
        "fat_100g": round(fat_100, 1),
        "carbs_100g": round(carbs_100, 1),
    }

    return total, not_found


def load_cache(path: Path) -> list[IngredientRecord]:
    """
    Загружает кэш не найденных ингредиентов.

    Если файл отсутствует или повреждён, возвращает пустой список.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_or_increment_cache(path: Path, items: list[str]) -> None:
    """
    Добавляет не найденные ингредиенты в кэш или увеличивает счётчик lookup_count.

    Используется для дальнейшего ручного пополнения базы ингредиентов.
    """
    if not items:
        return

    cache_data = load_cache(path)

    for item in items:
        normalized_item = normalize_name(item)

        if not normalized_item:
            continue

        search_lower = normalized_item.lower()
        found = False

        for record in cache_data:
            if (
                search_lower == record["id"].lower()
                or search_lower == record["name_ru"].lower()
                or any(search_lower == alias.lower() for alias in record["aliases_ru"])
                or search_lower == record["name_en"].lower()
                or any(search_lower == alias.lower() for alias in record["aliases_en"])
            ):
                record["lookup_count"] += 1
                found = True
                break

        if not found:
            record_json: IngredientRecord = {
                "id": normalized_item.replace(" ", "_"),
                "name_ru": normalized_item,
                "name_en": "",
                "aliases_ru": [],
                "aliases_en": [],
                "kcal_per_100g": 0,
                "protein_per_100g": 0,
                "fat_per_100g": 0,
                "carbs_per_100g": 0,
                "category": "",
                "region": ["ru", "eu"],
                "unit": "g",
                "source": "usda_cache",
                "usda_id": None,
                "lookup_count": 1,
                "migrated": False,
            }
            cache_data.append(record_json)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)


def footer_recipe(total: NutritionTotal) -> str:
    """
    Формирует текстовый блок с пищевой ценностью блюда.
    """
    return f""" 
Пищевая ценность (на весь рецепт):
Калорийность: {total["kcal"]} ккал
Белки: {total["protein"]} г
Жиры: {total["fat"]} г
Углеводы: {total["carbs"]} г
Вес: {total["weight"]} г
На 100 г:
Калорийность: {total["kcal_100g"]} ккал
Белки: {total["protein_100g"]} г
Жиры: {total["fat_100g"]} г
Углеводы: {total["carbs_100g"]} г
"""


def clean_vision_output(text: str) -> str:
    """
    Очищает ответ vision-модели.

    Оставляет только строки с разделителем "—",
    убирает дубли, строки "по вкусу" и строки с китайскими символами.
    """
    if not text:
        return ""

    cleaned: list[str] = []
    seen: set[str] = set()

    for line in text.splitlines():
        if "—" not in line:
            continue

        name = line.split("—")[0].strip()

        if "по вкусу" in line:
            continue

        if name in seen:
            continue

        if re.search(r"[\u4e00-\u9fff]", line):
            continue

        seen.add(name)
        cleaned.append(line)

    return "\n".join(cleaned)


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

    download_image(image_url, image_path)
    content = call_gigachat_vision(image_path, access_token)

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


def main() -> None:
    """
    Точка входа для локальной отладки режимов приложения.

    В Telegram-боте вместо этой функции будут использоваться обработчики сообщений.
    """
    mode = "photo"

    if mode == "recipe":
        user_message = "Составь рецепт на обед."
        ai_text = ask_ai(user_message=user_message, mode=mode)
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
        # image_url = "https://i.ibb.co/whzjRQ6Z/image.jpg"  # плов
        image_url = "https://i.ibb.co/sJsXgjSh/download.jpg"  # борщ
        result_text = handle_photo_mode(image_url)

    else:
        result_text = "Неизвестный режим"

    print(result_text)


if __name__ == "__main__":
    INDEX = load_ingredients_index(DATA_DIR / "ingredients.json")
    main()
