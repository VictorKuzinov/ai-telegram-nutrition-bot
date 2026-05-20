import re

ParsedIngredients = list[tuple[str, float]]
# ParsedIngredient = dict[str, str | float]
# ParsedIngredients = list[ParsedIngredient]

def parse_ingredients(text: str) -> ParsedIngredients:
    """
    Извлекает из текста список продуктов и их вес.

    Поддерживает строки вида:
    - продукт — 100 г
    - продукт - 100 гр
    - продукт — 100 мл

    Единицы "шт." игнорируются, потому что пока нет пересчёта штук в граммы.
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
