import json
from pathlib import Path

from nutrition.nutrition_calc import IngredientRecord, normalize_name

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

cache_path = DATA_DIR / "missing_ingredients.json"

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