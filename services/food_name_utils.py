def normalize_food_log_name(food_name: str) -> str:
    food_name = food_name.strip()

    if not food_name:
        return food_name

    return food_name[:1].upper() + food_name[1:]