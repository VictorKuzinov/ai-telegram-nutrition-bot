import os
import json
import requests
import dotenv
from pathlib import Path

import pymorphy3
from deep_translator import GoogleTranslator

from nutrition.nutrition_cache import (
    load_cache,
    DATA_DIR,
    cache_path
)
from services.ingredient_lookup import build_aliases_index
from services.ingredient_normalization import NO_PLURAL_WORDS

dotenv.load_dotenv()

API_KEY = os.getenv("USDA_API_KEY")
morph = pymorphy3.MorphAnalyzer()

def get_cache_candidates(path: Path, min_lookup_count: int) -> list:
    candidates = []
    cache_data = load_cache(path)
    for item in cache_data:
        if item["lookup_count"] >= min_lookup_count and \
            item["migrated"] == False:
            candidates.append(item)
    return candidates
#
# def prepare_for_main_db_old(records):
#     for record in records:
#         confirmation = ""
#         while confirmation.lower() not in ("yes", "y", "да"):
#             record["name_en"] = input(f"Введите английский перевод слова - {record['name_ru']} в единственном числе: ")
#             record["aliases_en"] = input(f"Введите английский перевод слова - {record['name_ru']} во множественном числе: ")
#             record["aliases_ru"] = input(f"Введите значение слова: - {record['name_ru']} во множественном числе: ")
#             print(f"Вы ввели значение слова: {record['name_ru']} - во множественном числе: {record['aliases_ru']}"
#                   f" и его перевод на английский во множественном числе: {record['aliases_en']}, английский превод в единственном числе: {record["name_en"]}", sep="\n")
#             confirmation = input("Вы подтверждаете (Yes)?")
#     return records

def translate_to_en(name_ru: str) -> str:
    translated = (GoogleTranslator(source='auto', target='en').
        translate(name_ru)
    )

    return translated

def make_plural_ru(name_ru: str) -> str:
    name_ru = name_ru.lower().strip()

    if name_ru in NO_PLURAL_WORDS:
        return name_ru

    words = name_ru.lower().strip().split()

    plural_words = []

    for word in words:
        parsed = morph.parse(word)[0]

        plural = parsed.inflect({"plur"})

        if plural:
            plural_words.append(plural.word)
        else:
            plural_words.append(word)

    return " ".join(plural_words)

def prepare_for_main_db(records, aliases_index):
    prepared_records = []

    for record in records:
        name_ru = record["name_ru"]
        normalized_name = name_ru.lower().strip()

        if normalized_name in aliases_index:
            print(f"Уже есть в базе: {name_ru} -> {aliases_index[normalized_name]}")
            continue

        default_name_en = translate_to_en(name_ru)
        default_aliases_ru = make_plural_ru(name_ru)
        default_aliases_en = translate_to_en(default_aliases_ru)

        while True:
            print("\nНовый ингредиент:")
            print(f"Русское название: {name_ru}")
            print(f"EN ед. число: {default_name_en}")
            print(f"RU мн. число: {default_aliases_ru}")
            print(f"EN мн. число: {default_aliases_en}")

            confirmation = input("Подтвердить? [Y/n]: ").strip().lower()

            if confirmation in ("", "y", "yes", "да", "д"):
                record["name_en"] = default_name_en
                record["aliases_ru"] = [default_aliases_ru]
                record["aliases_en"] = [default_aliases_en]
                prepared_records.append(record)
                break

            record["name_en"] = input("Введите EN ед. число: ").strip()
            record["aliases_ru"] = [input("Введите RU мн. число: ").strip()]
            record["aliases_en"] = [input("Введите EN мн. число: ").strip()]

            confirmation = input("Теперь подтвердить? [Y/n]: ").strip().lower()

            if confirmation in ("", "y", "yes", "да", "д"):
                prepared_records.append(record)
                break

    return prepared_records

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
    aliases_ru.append(record["name_ru"])
    aliases_en.append(record["name_en"])
    record_json = {
        "id": record["name_en"].lower().replace( " ", "_"),
        "name_ru": record["name_ru"],
        "name_en": record["name_en"],
        "aliases_ru": aliases_ru,
        "aliases_en": aliases_en,
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
            print(f"Количество ингредиентов равно: {len(ingredient_data)}")
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

    with open(DATA_DIR / "ingredients.json", "r", encoding="utf-8") as f:
        ingredient_data = json.load(f)

    aliases_index = build_aliases_index(ingredient_data)

    prepared = prepare_for_main_db(candidates, aliases_index)

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
