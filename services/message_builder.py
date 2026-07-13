import re
from typing import TypedDict, TypeVar

from config_ai import FORBIDDEN_PRODUCTS
from nutrition.nutrition_calc import (
    ACTIVITY_LEVELS,
    TARGETS,
    calc_bmr,
    calc_base_calories,
    calc_energy_total,
    calculate_bju,
)
from services.message_ai_parser import (
    RecipeIngredients,
    parse_ingredients_recipe,
    RecipeIngredient,
    MenuIngredient,
    STOP_MARKERS,
)

T = TypeVar(
    "T",
    RecipeIngredient,
    MenuIngredient,
)

UNIT_TO_GRAMS = {
    "яйцо": 55,
    "яйца": 55,
    "яблоко": 150,
    "банан": 120,
    "помидор": 100,
    "огурец": 100,
}

TASTE_TO_GRAMS = {
    "соль": 5,
    "перец": 1,
    "сахар": 10,
    "паприка": 2,
    "карри": 2,
    "зелень": 10,
    "специи": 2,
    "чеснок": 5,
}

SPOON_TO_GRAMS = {
    "соль": {
        "1/2 чайной" : 3,
        "1/2 ч": 3,
        "чайная": 5,
        "ч": 5,
        "1/2 столовой": 12,
        "1/2 ст": 12,
        "столовая": 25,
        "ст": 25,
    },
    "перец": {
        "1/2 чайной" : 1,
        "1/2 ч": 1,
        "чайная": 2,
        "ч": 2,
        "1/2 столовой": 3,
        "1/2 ст": 3,
        "столовая": 6,
        "ст": 6,
    },
    "сахар": {
        "1/2 чайной": 2.5,
        "1/2 ч": 2.5,
        "чайная": 5,
        "ч": 5,
        "1/2 столовой": 10,
        "1/2 ст": 10,
        "столовая": 20,
        "ст": 20,
    },
}

KEEP_BASE_NAME_PRODUCTS = {
    "фарш",
}

AUTO_REPLACE_PRODUCTS = {
    "масло": "сливочное масло",
    "маслa": "сливочное масло",
    "орехи": "грецкий орех",
    "овощи": "огурец",
    "фрукты": "яблоко",
    "зелень": "укроп",
    "рыба": "треска",
    "мясо": "говядина",
    "хлеб": "хлеб пшеничный",
    "растительное масло": "подсолнечное масло",
    "смесь специй": "паприка",
    "специи": "паприка"
}

AUTO_REPLACE_RECIPE = {
    "масло": "подсолнечное масло",
    "орехи": "грецкий орех",
    "овощи": "огурец",
    "фрукты": "яблоко",
    "зелень": "укроп",
    "рыба": "треска",
    "мясо": "говядина",
    "хлеб": "хлеб пшеничный",
    "растительное масло": "подсолнечное масло",
}


class ParsedRecipe(TypedDict):
    title: str
    ingredients: RecipeIngredients
    steps: str


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
        r"-\s*(?P<name>[а-яёА-ЯЁ\s]+)\s*[—-]\s*(?P<count>\d+(?:[.,]\d+)?)\s*(шт|зубчик(?:а|ов)?)",
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

def normalize_taste_units(text: str) -> str:

    pattern = re.compile(
        r"-\s*(?P<name>[а-яёА-ЯЁ\s]+(?:\([^)]*\))?)\s*[—-]\s*по\s*вкусу",
        re.IGNORECASE,
    )

    def replace(match: re.Match) -> str:
        name = match.group("name").strip().lower()

        base_name = name.partition("(")[0].strip()

        if base_name in TASTE_TO_GRAMS:
            grams = TASTE_TO_GRAMS[base_name]
        else:
            return match.group(0)

        return f"- {name} — {grams} г"

    return pattern.sub(replace, text)

def normalize_spoon_units(text: str) -> str:
    pattern = re.compile(
        r"-\s*(?P<name>соль|перец)\s*[—-]\s*(?P<count>\d+(?:[.,]\d+)?)\s*(?P<spoon>чайная|ч\.?|столовая|ст\.?)\s+ложк[аи]?",
        re.IGNORECASE,
    )

    def replace(match: re.Match) -> str:
        name = match.group("name").lower()
        count = float(match.group("count").replace(",", "."))
        spoon = match.group("spoon").lower().replace(".", "")

        grams_per_spoon = SPOON_TO_GRAMS[name][spoon]
        grams = round(count * grams_per_spoon)

        return f"- {name} — {grams} г"

    return pattern.sub(replace, text)

def normalize_ai_markdown(text: str) -> str:
    text = text.replace("**", "")
    text = text.replace("__", "")
    return text

# def normalize_parentheses_products(ingredients: RecipeIngredients) -> RecipeIngredients:
#     result = []
#
#     for item in ingredients:
#         new_item = item.copy()
#         name = new_item["name"].strip().lower()
#
#         if name.startswith("мясо (") and name.endswith(")"):
#             inside = name.split("(", 1)[1].rstrip(")").strip()
#             first_product = inside.split(",")[0].strip()
#             new_item["name"] = first_product
#
#         elif name.startswith("рыба (") and name.endswith(")"):
#             inside = name.split("(", 1)[1].rstrip(")").strip()
#             first_product = inside.split(",")[0].strip()
#             new_item["name"] = first_product
#
#         elif name.startswith("овощи (") and name.endswith(")"):
#             inside = name.split("(", 1)[1].rstrip(")").strip()
#             first_product = inside.split(",")[0].strip()
#             new_item["name"] = first_product
#
#         elif name.startswith("зелень (") and name.endswith(")"):
#             inside = name.split("(", 1)[1].rstrip(")").strip()
#             first_product = inside.split(",")[0].strip()
#             new_item["name"] = first_product
#
#         result.append(new_item)
#
#     return result

def split_parentheses_products(
    ingredients: RecipeIngredients,
) -> RecipeIngredients:

    result: RecipeIngredients = []

    for item in ingredients:
        name = item["name"].strip().lower()
        weight = float(item["weight"])

        before, sep, after = name.partition("(")

        if not sep or ")" not in after:
            result.append(item)
            continue

        base_name = before.strip()

        if base_name in KEEP_BASE_NAME_PRODUCTS:
            new_item = item.copy()
            new_item["name"] = base_name
            result.append(new_item)
            continue

        if base_name not in FORBIDDEN_PRODUCTS:
            result.append(item)
            continue

        inside = after.partition(")")[0]

        products = [
            product.strip()
            for product in inside.split(",")
            if product.strip()
        ]

        if not products:
            result.append(item)
            continue

        base_weight = round(weight / len(products))
        weights = [base_weight] * len(products)
        diff = round(weight - sum(weights))
        weights[-1] += diff

        for product_name, product_weight in zip(products, weights):
            new_item = item.copy()
            new_item["name"] = product_name
            new_item["weight"] = float(product_weight)
            result.append(new_item)

    return result

def replace_generic_products(iingredients: list[T], mode: str) -> list[T]:
    result = []

    for item in iingredients:
        new_item = item.copy()
        name = new_item["name"].strip().lower()

        if mode == "recipe" and name in AUTO_REPLACE_PRODUCTS:
            new_item["name"] = AUTO_REPLACE_RECIPE[name]
        if mode == "menu" and name in FORBIDDEN_PRODUCTS:
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

def merge_duplicate_recipe_items(parsed_recipe: list[dict]) -> list[dict]:
    merged: dict[tuple[str, str], dict] = {}

    for item in parsed_recipe:

        name = item["name"].strip().lower()
        key = (name)

        if key not in merged:
            new_item = item.copy()
            new_item["name"] = name
            merged[key] = new_item
        else:
            merged[key]["weight"] += item["weight"]

    return list(merged.values())

def parse_recipe_blocks(text: str) -> ParsedRecipe:
    title = ""
    ingredients_block = ""
    steps = ""

    current_block = ""

    for line in text.splitlines():
        stripped = line.strip()
        stripped = stripped.strip("*_ ")

        if any(marker in stripped.lower() for marker in STOP_MARKERS):
            break

        if stripped.startswith("Название:"):
            current_block = "title"
            title = stripped.replace("Название:", "", 1).strip()
            continue

        if stripped.startswith("Ингредиенты:"):
            current_block = "ingredients"
            continue

        if stripped.startswith("Приготовление:"):
            current_block = "steps"
            continue

        if current_block == "ingredients":
            ingredients_block += line + "\n"

        elif current_block == "steps":
            steps += line + "\n"

    return {
        "title": title,
        "ingredients": parse_ingredients_recipe(ingredients_block),
        "steps": steps.strip(),
    }

def build_recipe_text(recipe: ParsedRecipe) -> str:
    lines = []

    lines.append(f"Название: {recipe['title']}")
    lines.append("")
    lines.append("Ингредиенты:")

    for item in recipe["ingredients"]:
        lines.append(f"- {item['name']} — {round(item['weight'])} г")

    lines.append("")
    lines.append("Приготовление:")
    lines.append(recipe["steps"])

    return "\n".join(lines).strip()

