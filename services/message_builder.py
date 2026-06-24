import re
from typing import TypedDict

from nutrition.nutrition_calc import (
    ACTIVITY_LEVELS,
    TARGETS,
    calc_bmr,
    calc_base_calories,
    calc_energy_total,
    calculate_bju,
)

UNIT_TO_GRAMS = {
    "яйцо": 55,
    "яйца": 55,
    "яблоко": 150,
    "банан": 120,
    "помидор": 100,
    "огурец": 100,
}

AUTO_REPLACE_PRODUCTS = {
    "масло": "сливочное масло",
    "орехи": "грецкий орех",
    "овощи": "огурец",
    "фрукты": "яблоко",
    "зелень": "укроп"
}

FORBIDDEN_PRODUCTS = {
    "овощи",
    "фрукты",
    "зелень",
    "орехи",
    "рыба",
    "мясо",
    "масло",
    "мясо",
    "сыр",
}




class ProfileResults(TypedDict):
    bmr: float
    base_calories: float
    total_energy: float
    bju: float


def calculate_profile_results(profile) -> ProfileResults:
    bmr = calc_bmr(
        gender=profile.gender,
        weight=profile.weight,
        height=profile.height,
        age=profile.age,
    )

    base_calories = round(
        calc_base_calories(
            bmr,
            activity_level=profile.activity,
        )
    )

    total_energy = calc_energy_total(
        base_calories,
        target=profile.target,
    )

    bju = calculate_bju(
        weight=profile.weight,
        total_energy=total_energy,
        goal=profile.target,
    )

    return {
        "bmr": bmr,
        "base_calories": base_calories,
        "total_energy": total_energy,
        "bju": bju,
    }

def build_calc_result_message(
    profile,
    results: dict,
) -> str:

    gender_title = (
        "Мужчина"
        if profile.gender == "M"
        else "Женщина"
    )

    return (
        f"📊 Ваш результат:\n\n"
        f"👤 Пол: {gender_title}\n"
        f"🔥 Основной обмен: "
        f"{round(results['bmr'])} ккал\n"
        f"⚡ Суточная норма: "
        f"{round(results['base_calories'])} ккал\n"
        f"🎯 Цель: "
        f"{TARGETS[profile.target]['title']}\n"
        f"🏃 Активность: "
        f"{ACTIVITY_LEVELS[profile.activity]['title']}\n"
        f"🍽 Рекомендуемая калорийность: "
        f"<b>{results['total_energy']}</b> ккал\n\n"
        f"🥩 Белки: "
        f"{results['bju']['protein']} г\n"
        f"🧈 Жиры: "
        f"{results['bju']['fat']} г\n"
        f"🍞 Углеводы: "
        f"{results['bju']['carbs']} г"
    )

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

def build_menu_text_from_parsed(parsed_menu: list[dict]) -> str:
    meals: dict[str, list[dict]] = {}

    for item in parsed_menu:
        meal = item["meal"]

        meals.setdefault(meal, []).append(item)

    lines = []

    for meal_name in ("завтрак", "обед", "ужин"):
        ingredients = meals.get(meal_name)

        if not ingredients:
            continue

        dish = ingredients[0].get("dish")

        lines.append(f"{meal_name.capitalize()}:")
        if dish:
            lines.append(f"Блюдо: {dish.capitalize()}")

        for item in ingredients:
            lines.append(
                f"- {item['name']} - {round(item['weight'])} г"
            )

        lines.append("")

    return "\n".join(lines).strip()

def scale_menu_weights(
    parsed_menu: list[dict],
    target_kcal: float,
    actual_kcal: float,
) -> list[dict]:
    if actual_kcal <= 0:
        return parsed_menu

    ratio = target_kcal / actual_kcal
    ratio = min(ratio, 1.5)

    scaled_menu = []

    for item in parsed_menu:
        new_item = item.copy()
        new_item["weight"] = round(item["weight"] * ratio)
        scaled_menu.append(new_item)

    return scaled_menu

def group_menu_by_meal(parsed_menu: list[dict]) -> dict[str, list[dict]]:
    meals: dict[str, list[dict]] = {}

    for item in parsed_menu:
        meal = item["meal"]
        meals.setdefault(meal, []).append(item)

    return meals

def normalize_piece_units(text: str) -> str:
    pattern = re.compile(
        r"-\s*(?P<name>[а-яёА-ЯЁ\s]+)\s*[—-]\s*(?P<count>\d+)\s*шт",
        re.IGNORECASE,
    )

    def replace(match: re.Match) -> str:
        name = match.group("name").strip().lower()
        count = int(match.group("count"))

        grams_per_piece = UNIT_TO_GRAMS.get(name)

        if grams_per_piece is None:
            return match.group(0)

        grams = count * grams_per_piece
        return f"- {name} — {grams} г"

    return pattern.sub(replace, text)

def replace_generic_products(parsed_menu: list[dict]) -> list[dict]:
    result = []

    for item in parsed_menu:
        new_item = item.copy()
        name = new_item["name"].strip().lower()

        if name in AUTO_REPLACE_PRODUCTS:
            new_item["name"] = AUTO_REPLACE_PRODUCTS[name]

        result.append(new_item)

    return result

def find_bad_items(menu: list[dict]) -> list[dict]:
    return [
        item["name"]
        for item in menu
        if item["name"].strip().lower() in FORBIDDEN_PRODUCTS
    ]

def merge_duplicate_items(parsed_menu: list[dict]) -> list[dict]:
    merged: dict[tuple[str, str], dict] = {}

    for item in parsed_menu:
        meal = item["meal"].strip().lower()
        name = item["name"].strip().lower()
        key = (meal, name)

        if key not in merged:
            new_item = item.copy()
            new_item["meal"] = meal
            new_item["name"] = name
            merged[key] = new_item
        else:
            merged[key]["weight"] += item["weight"]

    return list(merged.values())