from IPython.core.completer import not_found
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from numpy.random import set_state

from db.repositories import (
    get_today_food_logs,
    get_user_profile,
    get_food_logs_for_period, create_food_log,
)
from keyboards import (
    diary_menu_keyboard,
    main_menu_keyboard,
    change_diary_keyboard,
)
from nutrition.nutrition_cache import save_or_increment_cache, cache_path
from nutrition.nutrition_calc import TARGETS, calculate_nutrition, footer
from services.message_builder import calculate_profile_results
from states import DiaryForm

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
    message: Message,
    state: FSMContext,
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
        log_map = {}
        eaten = 0
        answer = ""
        for index, food in enumerate(foods, start=1):
            eaten += food.kcal
            log_map[str(index)] = food.id
            answer += f"{index}. {food.food_name} — {food.weight}г.\n"
            answer += f"🔥 {food.kcal} ккал | 🥩 {food.protein} | "\
                      f"🧈 {food.fat} | 🍞 {food.carbs}\n"

        await message.answer(answer)
        await state.update_data(log_map=log_map)
        summary = ('-' * 10 + f"\n🎯 Текущая цель: "
            f"{TARGETS[profile.target]['title']}\n"
            f"🍽 Калорийность: "
            f"<b>{total_energy}</b> ккал,\n"
            f"Съедено: <b>{eaten}</b> ккал,\n"
            f"Осталось: <b>{total_energy - eaten}</b> ккал,\n"
        )
        await message.answer(
            summary,
            reply_markup=change_diary_keyboard,
        )

@router.message(F.text == "➕ Добавить")
async def added_dish_diary_handler(
    message: Message,
    state: FSMContext,
) -> None:
    await state.set_state(DiaryForm.waiting_name)
    await message.answer("Введите название блюда.")

@router.message(DiaryForm.waiting_name)
async def dish_name_handler(
    message: Message,
    state: FSMContext,
) -> None:
    food_name = message.text.strip()

    if not food_name:
        await message.answer("Введите название блюда.")
        return

    await state.update_data(name=food_name)
    await state.set_state(DiaryForm.waiting_weight)
    await message.answer("Введите вес блюда в граммах.")

@router.message(DiaryForm.waiting_weight)
async def dish_weight_handler(
    message: Message,
    state: FSMContext,
) -> None:
    text = message.text.strip()

    if not text.isdigit():
        await message.answer("Введите вес числом в граммах.")
        return

    weight = int(text)

    if weight <= 0:
        await message.answer("Вес должен быть больше нуля.")
        return

    await state.update_data(weight=weight)
    data = await state.get_data()

    total, not_found = calculate_nutrition(
        [
            {
                "name": data["name"],
                "weight": data["weight"],
            }
        ]
    )

    if not_found:
        save_or_increment_cache(cache_path, not_found)
        await message.answer(
            "⚠️ Блюдо пока отсутствует в базе ингредиентов.\n"
            "Оно добавлено в очередь на обработку."
        )
        await state.clear()
        return

    profile = get_user_profile(message.from_user.id)

    if profile is None:
        await message.answer("Профиль пользователя не найден.")
        await state.clear()
        return

    food_log_data = {
        "user_id": profile.id,
        "food_name": data["name"],
        "weight": data["weight"],
        "kcal": total["kcal"],
        "protein": total["protein"],
        "fat": total["fat"],
        "carbs": total["carbs"],
        "source": "manual",
    }

    create_food_log(food_log_data)

    await message.answer(
        f"✅ Блюдо сохранено в Ваш дневник:\n\n"
        f"🍽 {food_log_data['food_name']}\n"
        f"⚖️ Вес: {food_log_data['weight']} г"
    )

    await message.answer(
        footer(total, "recipe")
    )

    await state.clear()

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
        results = calculate_profile_results(profile)
        total_energy = results["total_energy"]
        await message.answer(f"🔥 Осталось: {total_energy} ккал.")
        await message.answer("Вы не потребляли еще калории сегодня.")
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
    await message.answer("📅 История питания 7 дней:")
    telegram_id = message.from_user.id
    profile = get_user_profile(message.from_user.id)
    if profile is None:
        await message.answer("Профиль пользователя не найден.")
        return
    history = get_food_logs_for_period(telegram_id, days=7)
    if len(history) == 0:
        await message.answer("Ваша история питания за это период пока пустая.")
        return
    answer = ""
    for date, total_kcal in history:
        answer += (
            f"📌 {date} | "
            f" 🔥 {round(total_kcal)} ккал\n\n"
        )
    await message.answer(answer)