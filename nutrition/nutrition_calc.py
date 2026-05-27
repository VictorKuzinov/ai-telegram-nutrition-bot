import re
import json
from pathlib import Path
from typing import Any

from services.message_ai_parser import ParsedIngredients

NutritionTotal = dict[str, float]
IngredientRecord = dict[str, Any]

ACTIVITY_LEVELS = {
    "sedentary": {
        "title": "Сидячий образ жизни",
        "factor": 1.2,
    },
    "light": {
        "title": "Лёгкая активность",
        "factor": 1.375,
    },
    "moderate": {
        "title": "Средняя активность",
        "factor": 1.55,
    },
    "high": {
        "title": "Высокая активность",
        "factor": 1.725,
    },
    "extreme": {
        "title": "Очень высокая активность",
        "factor": 1.9,
    },
}

TARGETS = {
    "loss": {
        "title": "Похудение",
        "calorie_factor": 0.85,
        "protein_factor": 1.8,
        "fat_factor": 0.9,
    },
    "maintain": {
        "title": "Поддержание веса",
        "calorie_factor": 1.0,
        "protein_factor": 1.6,
        "fat_factor": 1.0,
    },
    "gain": {
        "title": "Набор массы",
        "calorie_factor": 1.15,
        "protein_factor": 2.0,
        "fat_factor": 1.0,
    },
}

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

def calc_bmr(
    gender: str,
    weight: float,
    height: float,
    age: int,
) -> float:

    if gender == "M":
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
    else:
        bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161

    return bmr


def calc_base_calories(
    bmr: float,
    activity_level: str,
) -> float:

    calories_base = (
        bmr * ACTIVITY_LEVELS.get(activity_level)["factor"]
    )

    return calories_base


def calc_energy_total(
    calories: float,
    target: str,
) -> float:

    return round(
        calories * TARGETS.get(target)["calorie_factor"]
    )

def calculate_bju(
        weight: float,
        total_energy: float,
        goal: str,
) -> dict[str, float]:

    protein = round(weight * TARGETS.get(goal)["protein_factor"])
    fat = round(weight * TARGETS.get(goal)["fat_factor"])
    carbs = round((total_energy - protein * 4 - fat * 9) / 4)

    return {"protein": protein,
            "fat": fat,
            "carbs": carbs}

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

INDEX: dict[str, IngredientRecord] = load_ingredients_index(
    DATA_DIR / "ingredients.json"
)

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

    for ingredient in parsed_ingredients:
        name = ingredient["name"]
        grams = ingredient["weight"]

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

def footer(total: NutritionTotal, mode: str) -> str:
    """
    Формирует текстовый блок с пищевой ценностью блюда.
    """
    if mode == "menu":
        title = "Пищевая ценность приёма пищи"
    else:
        title = "Пищевая ценность (на весь рецепт)"
    return f"""
🍽 <b>{title}:</b>

🔥 Калорийность: {total["kcal"]} ккал
🥩 Белки: {total["protein"]} г
🧈 Жиры: {total["fat"]} г
🍞 Углеводы: {total["carbs"]} г
⚖️ Вес: {total["weight"]} г

📊 <b>На 100 г:</b>

🔥 Калорийность: {total["kcal_100g"]} ккал
🥩 Белки: {total["protein_100g"]} г
🧈 Жиры: {total["fat_100g"]} г
🍞 Углеводы: {total["carbs_100g"]} г
"""

def calculate_nutrition_menu(parsed_ingredients: ParsedIngredients) -> tuple[NutritionTotal, list[str]]:
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

    for ingredient in parsed_ingredients:
        name = ingredient["name"]
        grams = ingredient["weight"]

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