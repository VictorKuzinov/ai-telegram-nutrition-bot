import json
import os
import dotenv
from pathlib import Path

from nutrition.nutrition_cache import load_cache
from services.ingredient_lookup import build_aliases_index
from services.sync_usda_candidates import translate_to_en, make_plural_ru, fetch_usda_data, normalize_usda, \
    transform_to_internal, append_to_main_db

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

dish_path = DATA_DIR / "review_dishes.json"

dotenv.load_dotenv()

API_KEY = os.getenv("USDA_API_KEY")

def get_dishes_candidates(path: Path) -> list:
    candidates = []
    cache_data = load_cache(path)
    for item in cache_data:
        if item["status"]  == "pending":
            candidates.append(item)
    return candidates

def build_food_from_ai(record: dict) -> dict | None:
    if record is None:
        return None

    name_en = record["name_en"].strip().lower()

    return {
        "id": name_en.replace(" ", "_"),
        "name_ru": record["name_ru"],
        "name_en": record["name_en"],
        "aliases_ru": record.get("aliases_ru", []),
        "aliases_en": record.get("aliases_en", []),
        "kcal_per_100g": record["kcal_per_100g"],
        "protein_per_100g": record["protein_per_100g"],
        "fat_per_100g": record["fat_per_100g"],
        "carbs_per_100g": record["carbs_per_100g"],
        "category": "dish",
        "region": ["ru", "eu"],
        "unit": "g",
        "source": "ai_review",
    }


def build_food_from_manual(record: dict) -> dict|None:
    if record is None:
        return None

    name_ru = record["name_ru"].strip().lower()
    name_en = record["name_en"].strip().lower()
    print("\nНовое блюдо:")
    print(f"Русское название: {name_ru}")
    print(f"Английское название: {name_en}")
    while True:
        record["kcal_per_100g"] = float(input("Введите калории на 100 грамм: ").strip())
        record["protein_per_100g"] = float(input("Введите белок на 100 грамм: ").strip())
        record["fat_per_100g"] = float(input("Введите жиры на 100 грамм: ").strip())
        record["carbs_per_100g"] = float(input("Введите углеводы на 100 грамм: ").strip())

        confirmation = input("Подтвердить? [Y/n]: ").strip().lower()

        if confirmation in ("", "y", "yes", "да", "д"):
            return {
                "id": name_en.replace(" ", "_"),
                "name_ru": record["name_ru"],
                "name_en": record["name_en"],
                "aliases_ru": record.get("aliases_ru", []),
                "aliases_en": record.get("aliases_en", []),
                "kcal_per_100g": record["kcal_per_100g"],
                "protein_per_100g": record["protein_per_100g"],
                "fat_per_100g": record["fat_per_100g"],
                "carbs_per_100g": record["carbs_per_100g"],
                "category": "dish",
                "region": ["ru", "eu"],
                "unit": "g",
                "source": "ai_review",
            }
        elif confirmation in ("n", "no", "нет", "н"):
            print("Пропущено")
            return None

def compare_ai_usda(record_one: dict, record_two: dict) -> None:
    if record_one:
        name_ru = record_one["name_ru"].strip().lower()
        name_en = record_one["name_en"].strip().lower()
        print("\nНовое блюдо:")
        print(f"Русское название: {name_ru}")
        print(f"Английское название: {name_en}")
        print("AI:")
        print("Ккал:", record_one["kcal_per_100g"])
        print("Белки:", record_one["protein_per_100g"])
        print("Жиры:", record_one["fat_per_100g"])
        print("Углеводы:", record_one["carbs_per_100g"], "\n")
        print("USDA:")
        print("Ккал:", record_two["kcal_per_100g"])
        print("Белки:", record_two["protein_per_100g"])
        print("Жиры:", record_two["fat_per_100g"])
        print("Углеводы:", record_two["carbs_per_100g"])


def add_as_new_food(record: dict, aliases: dict) -> dict | None:
    name_dish = record["name_ru"].strip().lower()

    confirmation = input(f"Будем добавлять: {name_dish} [Y/n]: ").strip().lower()

    if confirmation in ("n", "no", "нет", "н"):
        print("Пропущено")
        return None

    if confirmation not in ("", "y", "yes", "да", "д"):
        print("Неизвестный ответ, пропускаю")
        return None

    record = approve_new_food(record, aliases)

    if not record:
        return None

    print("Подготовлена запись:", record)

    usda_data = fetch_usda_data(record["name_en"])

    print("AI estimate:")
    print(record)

    if usda_data:
        print("USDA candidate:")
        print(usda_data["description"])
        print(normalize_usda(usda_data))
    else:
        print("USDA ничего не нашла")

    while True:
        if usda_data:
            choice = input("Что взять? [1-AI / 2-USDA / 3-manual / 4-skip / 5-compare]: ").strip()
        else:
            choice = input("Что взять? [1-AI / 3-manual / 4-skip]: ").strip()

        if choice == "1":
            return build_food_from_ai(record)

        if choice == "2":
            if not usda_data:
                print("USDA-данных нет")
                continue
            return transform_to_internal(record, usda_data)

        if choice == "3":
            return build_food_from_manual(record)

        if choice == "4":
            print("Пропущено")
            return None

        if choice == "5":
            if not usda_data:
                print("Сравнение невозможно: USDA ничего не нашла")
                continue

            compare_ai_usda(record, normalize_usda(usda_data))
            continue

        print("Неизвестный вариант, выберите снова.")

def approve_new_food(record: dict, aliases_index: dict) -> dict|None:

    name_ru = record["name_ru"]
    normalized_name = name_ru.lower().strip()

    if normalized_name in aliases_index:
        print(f"Уже есть в базе: {name_ru} -> {aliases_index[normalized_name]}")
        return
    default_name_en = translate_to_en(name_ru).strip().lower()
    default_aliases_ru = make_plural_ru(name_ru).strip().lower()
    default_aliases_en = translate_to_en(default_aliases_ru).strip().lower()

    while True:
        print("\nНовый ингредиент:")
        print(f"Русское название: {name_ru}")
        print(f"RU мн. число: {default_aliases_ru}")
        print(f"EN ед. число: {default_name_en}")
        print(f"EN мн. число: {default_aliases_en}")

        confirmation = input("Подтвердить? [Y/n]: ").strip().lower()

        if confirmation in ("", "y", "yes", "да", "д"):
            record["name_en"] = default_name_en
            record["aliases_ru"] = [default_aliases_ru]
            record["aliases_en"] = [default_aliases_en]
            break

        record["aliases_ru"] = [input("Введите RU мн. число: ").strip()]
        record["name_en"] = input("Введите EN ед. число: ").strip()
        record["aliases_en"] = [input("Введите EN мн. число: ").strip()]

        confirmation = input("Теперь подтвердить? [Y/n]: ").strip().lower()

        if confirmation in ("", "y", "yes", "да", "д"):
            break

    return record


def mark_review_dish_as_approved(record) -> None:
    if record is None:
        print("Данных для миграции нет.")
        return
    found = False
    data_dish = load_cache(dish_path)
    for item in data_dish:
        record_lower = item["name_ru"].lower()
        if record_lower == record["name_ru"].lower():
            item["status"] = "approved"
            found = True
            break
    if found:
        with open(dish_path, "w", encoding="utf-8") as f:
            json.dump(data_dish, f, ensure_ascii=False, indent=2)
