import re

RECIPE_REQUIRED_PRODUCTS = {
    "плов": [
        {"рис"},
        {"говядина", "баранина", "курица, свинина"},
    ],
    "долм": [
        {"виноградные листья", "листья винограда"},
        {"фарш"},
    ],
    "уха": [
        {"рыба"},
        {"картошка", "лук"}
    ],
    "шурп": [
        {"вода", "бульон"},
        {"баранина", "говядина", "курица"},
        {"картофель"},
    ],
}

def extract_recipe_name(text: str) -> str | None:
    match = re.search(
        r"^\s*\*{0,2}Название:?\*{0,2}\s*(.+)$",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )

    if match:
        return match.group(1).strip()

    return None


def get_required_ingredients(recipe_name: str) -> list[set[str]] | None:
    recipe_name = recipe_name.lower().strip()

    for recipe_key, groups in RECIPE_REQUIRED_PRODUCTS.items():
        if recipe_key in recipe_name:
            return groups

    return None

def format_required_ingredients(groups: list[set[str]]) -> str:
    lines = []

    for group in groups:
        lines.append(f"- {sorted(group)[0]}")

    return "\n".join(lines)