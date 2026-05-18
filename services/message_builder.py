from nutrition.nutrition_calc import (
    ACTIVITY_LEVELS,
    TARGETS,
    calc_bmr,
    calc_base_calories,
    calc_energy_total,
    calculate_bju,
)


def calculate_profile_results(profile) -> dict:
    bmr = calc_bmr(
        gender=profile.gender,
        weight=profile.weight,
        height=profile.height,
        age=profile.age,
    )

    base_calories = round(
        calc_base_calories(
            bmr,
            activity_level=profile.activity,
        )
    )

    total_energy = calc_energy_total(
        base_calories,
        target=profile.target,
    )

    bju = calculate_bju(
        weight=profile.weight,
        total_energy=total_energy,
        goal=profile.target,
    )

    return {
        "bmr": bmr,
        "base_calories": base_calories,
        "total_energy": total_energy,
        "bju": bju,
    }

def build_calc_result_message(
    profile,
    results: dict,
) -> str:

    gender_title = (
        "Мужчина"
        if profile.gender == "M"
        else "Женщина"
    )

    return (
        f"📊 Ваш результат:\n\n"
        f"👤 Пол: {gender_title}\n"
        f"🔥 Основной обмен: "
        f"{round(results['bmr'])} ккал\n"
        f"⚡ Суточная норма: "
        f"{round(results['base_calories'])} ккал\n"
        f"🎯 Цель: "
        f"{TARGETS[profile.target]['title']}\n"
        f"🏃 Активность: "
        f"{ACTIVITY_LEVELS[profile.activity]['title']}\n"
        f"🍽 Рекомендуемая калорийность: "
        f"<b>{results['total_energy']}</b> ккал\n\n"
        f"🥩 Белки: "
        f"{results['bju']['protein']} г\n"
        f"🧈 Жиры: "
        f"{results['bju']['fat']} г\n"
        f"🍞 Углеводы: "
        f"{results['bju']['carbs']} г"
    )