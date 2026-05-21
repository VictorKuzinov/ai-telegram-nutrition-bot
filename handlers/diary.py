from aiogram import Router, F
from aiogram.types import Message

from db.repositories import get_today_food_logs, get_user_profile
from keyboards import (
    diary_menu_keyboard,
    main_menu_keyboard,
)
from nutrition.nutrition_calc import TARGETS
from services.message_builder import calculate_profile_results

router = Router()

@router.message(F.text == "📖 Дневник")
async def diary_menu_handler(
    message: Message,
) -> None:
    await message.answer(
        "Раздел дневника питания:",
        reply_markup=diary_menu_keyboard,
    )

@router.message(F.text == "⬅️ Назад")
async def back_to_main_menu_handler(
    message: Message,
) -> None:

    await message.answer(
        "Главное меню:",
        reply_markup=main_menu_keyboard,
    )

@router.message(F.text == "🍽 Сегодня")
async def today_eaten_diary_handler(
    message: Message
) -> None:

    await message.answer("Дневник питания:\n🍽 Сегодня")
    telegram_id = message.from_user.id
    profile = get_user_profile(message.from_user.id)
    if profile is None:
        await message.answer("Профиль пользователя не найден.")
        return
    foods = get_today_food_logs(telegram_id)
    if len(foods) == 0:
        await message.answer("Ваш журнал пока пуст.")
    else:
        results = calculate_profile_results(profile)
        total_energy = results["total_energy"]
        eaten = 0
        answer = ""
        for food in foods:
            eaten += food.kcal
            answer += f"• {food.food_name} — {food.weight}г.\n"
            answer += f"🔥 {food.kcal} ккал | 🥩 {food.protein} | "\
                      f"🧈 {food.fat} | 🍞 {food.carbs}\n"

        await message.answer(answer)
        summary = ('-' * 10 + f"\n🎯 Текущая цель: "
            f"{TARGETS[profile.target]['title']}\n"
            f"🍽 Калорийность: "
            f"<b>{total_energy}</b> ккал,\n"
            f"Съедено: <b>{eaten}</b> ккал,\n"
            f"Осталось: <b>{total_energy - eaten}</b> ккал,\n"
        )
        await message.answer(summary)

@router.message(F.text == "🔥 Остаток")
async def remainder_kcal_handler(
    message: Message
) -> None:
    await message.answer("На сегодня осталось :\n")
    telegram_id = message.from_user.id
    profile = get_user_profile(message.from_user.id)
    if profile is None:
        await message.answer("Профиль пользователя не найден.")
        return
    foods = get_today_food_logs(telegram_id)
    if len(foods) == 0:
        await message.answer("Вы не потребляли еще калории.")
    else:
        results = calculate_profile_results(profile)
        total_energy = results["total_energy"]
        eaten = sum(food.kcal for food in foods)
        remainder = round(total_energy - eaten)
        if remainder > 0:
            await message.answer(f"🔥 Осталось: {remainder} ккал.")
        elif remainder == 0:
            await message.answer(
                "🙏 Вы идеально уложились в дневную норму калорий."
            )
        else:
            await message.answer(
                f"⚠️ Лимит превышен на: {abs(remainder)} ккал."
            )

@router.message(F.text == "📅 История")
async def history_day_handler(    message: Message
) -> None:
    pass