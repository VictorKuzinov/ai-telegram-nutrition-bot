ACTIVITY_LEVELS = {
    "sedentary": {
        "title": "Сидячий образ жизни",
        "factor": 1.2,
    },
    "light": {
        "title": "Лёгкая активность",
        "factor": 1.375,
    },
    "moderate": {
        "title": "Средняя активность",
        "factor": 1.55,
    },
    "high": {
        "title": "Высокая активность",
        "factor": 1.725,
    },
    "extreme": {
        "title": "Очень высокая активность",
        "factor": 1.9,
    },
}

TARGETS = {
    "loss": {
        "title": "Похудение",
        "calorie_factor": 0.85,
        "protein_factor": 1.8,
        "fat_factor": 0.9,
    },
    "maintain": {
        "title": "Поддержание веса",
        "calorie_factor": 1.0,
        "protein_factor": 1.6,
        "fat_factor": 1.0,
    },
    "gain": {
        "title": "Набор массы",
        "calorie_factor": 1.15,
        "protein_factor": 2.0,
        "fat_factor": 1.0,
    },
}


def calc_bmr(
    gender: str,
    weight: float,
    height: float,
    age: int,
) -> float:

    if gender == "M":
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
    else:
        bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161

    return bmr


def calc_base_calories(
    bmr: float,
    activity_level: str,
) -> float:

    calories_base = (
        bmr * ACTIVITY_LEVELS.get(activity_level)["factor"]
    )

    return calories_base


def calc_energy_total(
    calories: float,
    target: str,
) -> float:

    return round(
        calories * TARGETS.get(target)["calorie_factor"]
    )

def calculate_bju(
        weight: float,
        total_energy: float,
        goal: str,
) -> dict[str, float]:

    protein = round(weight * TARGETS.get(goal)["protein_factor"])
    fat = round(weight * TARGETS.get(goal)["fat_factor"])
    carbs = round((total_energy - protein * 4 - fat * 9) / 4)

    return {"protein": protein,
            "fat": fat,
            "carbs": carbs}



def main():

    gender = "M"
    weight = 92
    height = 176
    age = 60
    goal = "loss"

    bmr = calc_bmr(gender, weight, height, age)
    print(f"BMR: {bmr}")

    calories = calc_base_calories(
        bmr,
        activity_level="moderate",
    )

    print(
        f"Выбранный уровень активности: "
        f"{ACTIVITY_LEVELS.get('moderate')['title']}, "
        f"CALORIES: {calories}"
    )

    total_energy = calc_energy_total(
        calories,
        target="loss",
    )

    print(
        f"Выбрана цель: "
        f"{TARGETS.get(goal)['title']}, "
        f"TOTAL ENERGY: {total_energy}"
    )

    print(calculate_bju(weight, total_energy, goal))

if __name__ == "__main__":
    main()