import re

from config_ai import choice_menu

ParsedIngredient = dict[str, str | float]
ParsedIngredients = list[ParsedIngredient]


FORBIDDEN_PATTERNS: list[str] = [
    r"\bккал\b",
    r"\bкалори",
    r"\bБЖУ\b",
    r"\bКБЖУ\b",
    r"\bбелк",
    r"\bжир",
    r"\bуглевод",
    r"\bэнергетическ",
    r"\bпищев(ая|ую)\s+ценност",
]


def parse_ingredient_line(text: str) -> tuple[str, float] | None:
    """
    Извлекает из одной строки название ингредиента и вес.

    Поддерживает форматы:
    - продукт — 100 г
    - продукт - 100 гр
    - продукт — 100 мл
    - продукт — 2 шт

    Перед разбором нормализует строку:
    - убирает символы таблиц "|";
    - приводит длинные тире к обычному "-";
    - убирает точки после единиц измерения.

    :param text: Строка с ингредиентом.
    :return: Кортеж (название, вес в граммах) или None, если строка не распознана.
    """
    text = text.lower().strip()

    text = text.replace("|", "")
    text = text.replace("—", "-")
    text = text.replace("–", "-")

    text = text.replace("шт.", "шт")
    text = text.replace("гр.", "гр")
    text = text.replace("г.", "г")
    text = text.replace("мл.", "мл")

    match = re.search(
        r"(.+?)\s*-\s*(\d+(?:[.,]\d+)?)\s*(г|гр|мл|шт)",
        text,
    )

    if not match:
        return None

    name = match.group(1).strip()
    name = name.lstrip("- ").strip()

    amount = float(match.group(2).replace(",", "."))
    unit = match.group(3).strip()

    if unit not in ("г", "гр", "мл"):
        return None

    return name, amount


def parse_ingredients_recipe(text: str) -> ParsedIngredients:
    """
    Извлекает ингредиенты из текста рецепта.

    Возвращает плоский список ингредиентов без привязки к приёму пищи.

    :param text: Текст рецепта от ИИ.
    :return: Список словарей с ключами name и weight.
    """
    parsed: ParsedIngredients = []

    for line in text.splitlines():
        result = parse_ingredient_line(line)

        if not result:
            continue

        parsed.append(
            {
                "name": result[0],
                "weight": result[1],
            }
        )

    return parsed


def parse_ingredients_menu(text: str) -> ParsedIngredients:
    """
    Извлекает ингредиенты из текста дневного меню.

    В отличие от parse_ingredients_recipe(), сохраняет тип приёма пищи
    в поле meal и название блюда dish.

    Поддерживаемые секции берутся из choice_menu:
    завтрак, обед, ужин, перекус.

    :param text: Текст меню от ИИ.
    :return: Список словарей с ключами meal, name и weight.
    """
    parsed: ParsedIngredients = []
    current_meal: str | None = None
    dish_name: str | None = None

    for line in text.splitlines():
        lower_line = line.lower().strip()

        if lower_line.endswith(":"):
            meal_name = lower_line.replace(":", "")

            if meal_name in choice_menu:
                current_meal = meal_name
                dish_name = None

            continue

        if lower_line.startswith("блюдо:"):
            dish_name = line.split(":", 1)[1].strip()
            continue

        if current_meal is None:
            continue

        result = parse_ingredient_line(line)

        if not result:
            continue

        parsed.append(
            {
                "meal": current_meal,
                "dish": dish_name,
                "name": result[0],
                "weight": result[1],
            }
        )

    return parsed


def clean_recipe_output(text: str) -> str:
    """
    Очищает текст рецепта от лишних блоков, которые может добавить ИИ.

    Удаляет строки с калорийностью, БЖУ, КБЖУ, пищевой ценностью
    и похожими комментариями. Оставляет только разрешённые блоки:
    - Название
    - Ингредиенты
    - Приготовление

    :param text: Исходный текст ответа ИИ.
    :return: Очищенный текст рецепта.
    """
    if not text:
        return ""

    lines = [line.rstrip() for line in text.splitlines()]
    kept: list[str] = []
    in_allowed_block = False

    for line in lines:
        stripped = line.strip()

        if not stripped:
            if kept:
                kept.append("")
            continue

        if any(
            re.search(pattern, stripped, flags=re.IGNORECASE)
            for pattern in FORBIDDEN_PATTERNS
        ):
            continue

        if stripped.startswith("Название:"):
            in_allowed_block = True
            kept.append(stripped)
            continue

        if stripped.startswith("Ингредиенты:") or stripped.startswith("Приготовление:"):
            in_allowed_block = True
            kept.append(stripped)
            continue

        if in_allowed_block:
            kept.append(stripped)

    result = "\n".join(kept).strip()
    result = re.sub(r"\n{3,}", "\n\n", result)
    result = re.sub(
        r"(?im)^.*(?:ккал|калори|БЖУ|КБЖУ|белк|жир|углевод|энергетическ|пищев).*$\n?",
        "",
        result,
    )

    return result.strip()

def clean_recipe_dish(text: str) -> str:
    """
    Очищает текст рецепта от лишних блоков, которые может добавить ИИ.

    Удаляет строки с калорийностью, БЖУ, КБЖУ, пищевой ценностью
    и похожими комментариями, приготовление. Оставляет только разрешённые блоки:
    - Название
    - Ингредиенты

    :param text: Исходный текст ответа ИИ.
    :return: Очищенный текст рецепта.
    """
    if not text:
        return ""

    lines = [line.rstrip() for line in text.splitlines()]
    kept: list[str] = []
    in_allowed_block = False

    for line in lines:
        stripped = line.strip()

        if not stripped:
            if kept:
                kept.append("")
            continue

        if any(
            re.search(pattern, stripped, flags=re.IGNORECASE)
            for pattern in FORBIDDEN_PATTERNS
        ):
            continue

        if stripped.startswith("Название:"):
            in_allowed_block = True
            kept.append(stripped)
            continue

        if stripped.startswith("Ингредиенты:"):
            in_allowed_block = True
            kept.append(stripped)
            continue

        if stripped.startswith("Приготовление:"):
            in_allowed_block = False
            kept.append(stripped)
            continue


        if in_allowed_block:
            kept.append(stripped)

    result = "\n".join(kept).strip()
    result = re.sub(r"\n{3,}", "\n\n", result)
    result = re.sub(
        r"(?im)^.*(?:ккал|калори|БЖУ|КБЖУ|белк|жир|углевод|энергетическ|пищев|приготов).*$\n?",
        "",
        result,
    )

    return result.strip()