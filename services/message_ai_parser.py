import re

ParsedIngredient = dict[str, str | float]
ParsedIngredients = list[ParsedIngredient]


FORBIDDEN_PATTERNS = [
    r'\bккал\b',
    r'\bкалори',
    r'\bБЖУ\b',
    r'\bКБЖУ\b',
    r'\bбелк',
    r'\bжир',
    r'\bуглевод',
    r'\bэнергетическ',
    r'\bпищев(ая|ую)\s+ценност',
]

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
            r"(.+?)\s*[—–-]\s*(\d+(?:[.,]\d+)?)\s*(г|гр|мл|шт)",
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

        parsed.append(
            {
                "name": name,
                "weight": amount,
            }
        )

    return parsed

def clean_recipe_output(text: str) -> str:
    if not text:
        return ""

    lines = [line.rstrip() for line in text.splitlines()]
    kept = []
    in_allowed_block = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if kept:
                kept.append("")
            continue

        if any(re.search(pat, stripped, flags=re.IGNORECASE) for pat in FORBIDDEN_PATTERNS):
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

    result = re.sub(r'\n{3,}', '\n\n', result)
    result = re.sub(r'(?im)^.*(?:ккал|калори|БЖУ|КБЖУ|белк|жир|углевод|энергетическ|пищев).*$\n?', '', result)

    return result.strip()