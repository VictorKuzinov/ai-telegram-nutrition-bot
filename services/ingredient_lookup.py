import json
from datetime import datetime

from rapidfuzz import process
from pydantic import BaseModel, Field, ValidationError

from ai.gigachat import get_access_token, call_gigachat, call_chat_with_fallback
from db.repositories import create_food_log
from nutrition.nutrition_cache import DATA_DIR


def build_aliases_index(ingredients: list[dict]) -> dict:
    aliases_index = {}

    for item in ingredients:
        values = [
            item.get("id"),
            item.get("name_ru"),
            item.get("name_en"),
            *item.get("aliases_ru", []),
            *item.get("aliases_en", []),
        ]

        for value in values:
            if not value:
                continue

            aliases_index[value.lower().strip()] = item

    return aliases_index


def find_candidates_by_fuzzy(user_text: str, aliases_index: dict, limit: int = 5) -> list[dict]:
    names = list(aliases_index.keys())

    matches = process.extract(
        user_text.lower().strip(),
        names,
        limit=limit,
    )

    candidates = []

    for name, score, _ in matches:
        item = aliases_index[name].copy()
        item["matched_alias"] = name
        item["fuzzy_score"] = score
        candidates.append(item)

    return candidates


def find_food_by_ai(access_token: str, user_text: str, aliases_index: dict) -> list[dict]:
    mode = "recipe"
    user_message = f"""
    Ты сопоставляешь название блюда пользователя с блюдами из моей базы.
    
    Пользователь ввёл:
        "{user_text}"
    
    Кандидаты из базы:
        {json.dumps(aliases_index, ensure_ascii=False, indent=2)}
    
    Задача:
        Выбери одно блюдо из кандидатов, если пользователь имел в виду его.
        Если подходящего блюда нет — верни null.
        Поле ai_confidence — твоя смысловая уверенность от 0.0 до 1.0.
        Не копируй fuzzy_score в ai_confidence
        Верни строго JSON без пояснений:
        {{
            "matched_id": "id блюда или null",
            "matched_name_ru": "название блюда или null",
            "ai_confidence": 0.0,
            "suggested_alias_ru": "{user_text}",
            "action": "add_alias | not_found",
            "reason": "короткое объяснение"
        }}
    """
    content = call_gigachat(access_token, mode=mode, user_prompt=user_message)
    if not content:
        return None

    return json.loads(content)


def get_item_by_id(candidates: list[dict], matched_id: str) -> dict | None:
    for item in candidates:
        if item["id"] == matched_id:
            return item
    return None


def calculate_nutrition_per_100g(item: dict, weight: float) -> dict:
    factor = weight / 100

    return {
        "name_ru": item["name_ru"],
        "kcal_per_100g": round(item["kcal"] / factor, 2),
        "protein_per_100g": round(item["protein"] / factor, 2),
        "fat_per_100g": round(item["fat"] / factor, 2),
        "carbs_per_100g": round(item["carbs"] / factor, 2),
        "source": "ai_estimate",
        "needs_review": True,
    }


class NutritionPer100g(BaseModel):
    kcal: float | None = None
    protein: float | None = None
    fat: float | None = None
    carbs: float | None = None


class AiDishEstimate(BaseModel):
    name_ru: str = Field(min_length=2, max_length=100)
    total_weight_g: float = Field(gt=0, lt=10000)
    nutrition_per_100g: NutritionPer100g


def validate_ai_estimate(dish: AiDishEstimate) -> tuple[bool, list[str]]:
    errors = []

    nutrition = dish.nutrition_per_100g

    if nutrition.kcal is None:
        errors.append("Отсутствует kcal")

    if nutrition.protein is None:
        errors.append("Отсутствует protein")

    if nutrition.fat is None:
        errors.append("Отсутствует fat")

    if nutrition.carbs is None:
        errors.append("Отсутствует carbs")

    return len(errors) == 0, errors


def calculate_portion_from_ai_estimate(
        estimate: AiDishEstimate,
        weight_g: float,
) -> dict:
    factor = weight_g / 100
    n = estimate.nutrition_per_100g

    return {
        "name_ru": estimate.name_ru,
        "weight_g": weight_g,
        "kcal": round(n.kcal * factor, 1),
        "protein": round(n.protein * factor, 1),
        "fat": round(n.fat * factor, 1),
        "carbs": round(n.carbs * factor, 1),
        "source": "ai_estimate",
        "needs_review": True,
    }


def get_ai_dish_estimate_with_retry(
    dish: str,
    max_attempts: int = 3,
) -> AiDishEstimate | None:
    last_error = ""

    for attempt in range(1, max_attempts + 1):
        user_prompt = f"""
Оцени КБЖУ блюда: {dish}.

Верни только валидный JSON строго такого формата:
{{
  "name_ru": "{dish}",
  "total_weight_g": 100,
  "nutrition_per_100g": {{
    "kcal": 0,
    "protein": 0,
    "fat": 0,
    "carbs": 0
  }}
}}

Обязательные условия:
- все поля обязательны;
- kcal должен быть числом больше 0;
- protein, fat, carbs должны быть числами больше или равны 0;
- не добавляй Markdown;
- не добавляй текст вне JSON.

Предыдущая ошибка:
{last_error}
"""

        content = call_chat_with_fallback(
            mode="dish",
            user_prompt=user_prompt,
        )

        if not content:
            last_error = "AI не вернул ответ"
            continue

        try:
            data = json.loads(content)
            estimate = AiDishEstimate.model_validate(data)

            is_valid, errors = validate_ai_estimate(estimate)

            if is_valid:
                return estimate

            last_error = "; ".join(errors)

        except json.JSONDecodeError:
            last_error = "Ответ не является валидным JSON"

        except ValidationError as error:
            last_error = str(error)

    return None


def normalize_name(name: str) -> str:
    return name.lower().strip()


def save_review_dish(dish: dict) -> None:
    path = DATA_DIR / "review_dishes.json"

    try:
        with open(path, "r", encoding="utf-8") as f:
            dishes = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        dishes = []

    new_name = normalize_name(dish["name_ru"])

    for item in dishes:
        if (
            normalize_name(item.get("name_ru", "")) == new_name
            and item.get("status") == "pending"
        ):
            item["repeat_count"] = item.get("repeat_count", 1) + 1
            item["last_seen_at"] = datetime.now().isoformat(timespec="seconds")

            with open(path, "w", encoding="utf-8") as f:
                json.dump(dishes, f, ensure_ascii=False, indent=2)
            return

    dish["repeat_count"] = 1
    dish["created_at"] = datetime.now().isoformat(timespec="seconds")
    dish["last_seen_at"] = dish["created_at"]

    dishes.append(dish)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(dishes, f, ensure_ascii=False, indent=2)


def build_food_log_record(
    user_id: int,
    portion: dict,
) -> dict:
    return {
        "user_id": user_id,
        "food_name": portion["name_ru"],
        "weight": portion["weight_g"],
        "kcal": portion["kcal"],
        "protein": portion["protein"],
        "fat": portion["fat"],
        "carbs": portion["carbs"],
        "source": portion["source"],
    }

def clean_dish_name(name: str) -> str:
    name = name.lower().strip()

    prefixes = (
        "ингредиенты:",
        "название:",
        "блюдо:",
        "-",
    )

    for prefix in prefixes:
        if name.startswith(prefix):
            name = name.removeprefix(prefix).strip()

    while name.startswith("-"):
        name = name[1:].strip()

    return name
