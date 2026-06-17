import re
from typing import TypedDict

from nutrition.nutrition_calc import (
    ACTIVITY_LEVELS,
    TARGETS,
    calc_bmr,
    calc_base_calories,
    calc_energy_total,
    calculate_bju,
)


class ProfileResults(TypedDict):
    bmr: float
    base_calories: float
    total_energy: float
    bju: float


def calculate_profile_results(profile) -> ProfileResults:
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

def filter_user_message(text: str) -> tuple[bool, str]:
    """
    Выполняет базовую фильтрацию пользовательского сообщения.

    Отсекает пустые, слишком короткие, бессмысленные сообщения
    и простые попытки prompt injection.

    Возвращает:
    - True и пустую строку, если сообщение допустимо;
    - False и текст ответа пользователю, если сообщение нужно отклонить.
    """
    text_lower = text.lower().strip()

    if not text_lower or len(text_lower) < 3:
        return False, "Пожалуйста, задайте вопрос по питанию."

    if len(set(text_lower)) < 3:
        return False, "Пожалуйста, задайте вопрос по питанию."

    suspicious_phrases = [
        "игнорируй инструкции",
        "забудь инструкции",
        "ты теперь",
        "system prompt",
        "act as",
        "ignore previous",
    ]

    if any(phrase in text_lower for phrase in suspicious_phrases):
        return False, "Я отвечаю только на вопросы по питанию."

    return True, ""

def clean_vision_output(text: str) -> str:
    """
    Очищает ответ vision-модели.

    Оставляет только строки с разделителем "—",
    убирает дубли, строки "по вкусу" и строки с китайскими символами.
    """
    if not text:
        return ""

    cleaned: list[str] = []
    seen: set[str] = set()

    for line in text.splitlines():
        if "—" not in line:
            continue

        name = line.split("—")[0].strip()

        if "по вкусу" in line:
            continue

        if name in seen:
            continue

        if re.search(r"[\u4e00-\u9fff]", line):
            continue

        seen.add(name)
        cleaned.append(line)

    return "\n".join(cleaned)