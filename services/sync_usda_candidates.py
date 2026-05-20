import os
import json

import requests
import dotenv
from pathlib import Path

from nutrition.nutrition_cache import load_cache, DATA_DIR, cache_path
dotenv.load_dotenv()

API_KEY = os.getenv("USDA_API_KEY")

def get_cache_candidates(path: Path, min_lookup_count: int) -> list:
    candidates = []
    cache_data = load_cache(path)
    for item in cache_data:
        if item["lookup_count"] >= min_lookup_count and \
            item["migrated"] == False:
            candidates.append(item)
    return candidates

def prepare_for_main_db(records):
    for record in records:
        confirmation = ""
        while confirmation.lower() not in ("yes", "y", "да"):
            record["name_en"] = input(f"Введите английский перевод слова - {record['name_ru']} в единственном числе: ")
            record["aliases_en"] = input(f"Введите английский перевод слова - {record['name_ru']} во множественном числе: ")
            record["aliases_ru"] = input(f"Введите значение слова: - {record['name_ru']} во множественном числе: ")
            print(f"Вы ввели значение слова: {record['name_ru']} - во множественном числе: {record['aliases_ru']}"
                  f" и его перевод на английский во множественном числе: {record['aliases_en']}, английский превод в единственном числе: {record["name_en"]}", sep="\n")
            confirmation = input("Вы подтверждаете (Yes)?")
    return records

def fetch_usda_data(query: str, api_key = API_KEY) -> dict | None:
    url = "https://api.nal.usda.gov/fdc/v1/foods/search"

    params = {
        "query": query,
        "api_key": api_key
    }

    response = requests.get(url, params=params, timeout=10)

    if response.ok:
        data = response.json()
        foods = data.get("foods", [])
        with open(query, "w", encoding="utf-8") as f:
            json.dump(foods, f, ensure_ascii=False, indent=2)
        if not foods:
            return None
        selected_food = foods[0]
        for food in foods:
            if food["dataType"] != "Branded":
                selected_food = food
                break
        print(selected_food)
    else:
        food = None

    return food

def normalize_usda(food: dict) -> dict:
    nutrients = {n["nutrientName"]: n["value"] for n in food["foodNutrients"]}

    return {
        "id": food["fdcId"],
        "kcal_per_100g": nutrients.get("Energy", 0),
        "protein_per_100g": nutrients.get("Protein", 0),
        "fat_per_100g": nutrients.get("Total lipid (fat)", 0),
        "carbs_per_100g": nutrients.get("Carbohydrate, by difference", 0),
        "category": nutrients.get("foodCategory", ""),
        "source": "usda",
    }

def transform_to_internal(record, data_usda) -> dict|None:
    if data_usda is None:
        return None
    data_usda = normalize_usda(data_usda)
    aliases_ru = []
    aliases_en = []
    record_json = {
        "id": record["name_en"].lower().replace( " ", "_"),
        "name_ru": record["name_ru"],
        "name_en": record["name_en"],
        "aliases_ru": aliases_ru.append(record["aliases_ru"]),
        "aliases_en": aliases_en.append(record["aliases_en"]),
        "kcal_per_100g": data_usda["kcal_per_100g"],
        "protein_per_100g": data_usda["protein_per_100g"],
        "fat_per_100g": data_usda["fat_per_100g"],
        "carbs_per_100g": data_usda["carbs_per_100g"],
        "category": data_usda["category"],
        "region": ["ru", "eu"],
        "unit": "g",
        "source": "local"
    }

    return record_json

def append_to_main_db(item: dict) -> None:
    if item is None:
        print("Данных для добавления нет.")
        return
    try:
        with open(DATA_DIR / "ingredients.json", 'r', encoding='utf-8') as f:
            ingredient_data = json.load(f)
            print(f"Клличество ингедиенов равно: {len(ingredient_data)}")
    except (FileNotFoundError, json.JSONDecodeError):
        ingredient_data = []
    for record in ingredient_data:
        record_lower = record["id"].lower()
        if record_lower == item["id"].lower():
            return
    print(f"Добавлен : {item['name_ru']} ингредиент")
    ingredient_data.append(item)
    with open(DATA_DIR / "ingredients.json", "w", encoding="utf-8") as f:
        json.dump(ingredient_data, f, ensure_ascii=False, indent=2)

def mark_as_migrated(item) -> None:
    if item is None:
        print("Данных для миграции нет.")
        return
    found = False
    data_cache = load_cache(cache_path)
    for record in data_cache:
        record_lower = record["id"].lower()
        if record_lower == item["id"].lower():
            record["migrated"] = True
            found = True
            break
    if found:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data_cache, f, ensure_ascii=False, indent=2)


def main():
    candidates = get_cache_candidates(cache_path, min_lookup_count = 3)

    if not candidates:
        print("Нет кандидатов")
        return

    prepared = prepare_for_main_db(candidates)

    for item in prepared:
        usda_data = fetch_usda_data(item["name_en"])

        if not usda_data:
            continue

        record = transform_to_internal(item, usda_data)

        append_to_main_db(record)

        mark_as_migrated(item)
        print(record)

if __name__ == "__main__":
    main()
