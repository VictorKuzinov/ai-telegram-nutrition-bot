from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from db.repositories import (
    get_today_food_logs,
    get_user_profile,
    get_food_logs_for_period,
    create_food_log,
    get_food_log_by_id,
    delete_food_log,
    update_food_log, get_food_stats_by_days,
)
from keyboards import (
    diary_menu_keyboard,
    change_diary_keyboard,
    main_menu_keyboard,
    statistics_menu_keyboard,
)
from nutrition.nutrition_cache import (
    save_or_increment_cache,
    cache_path,
)
from nutrition.nutrition_calc import (
    TARGETS,
    calculate_nutrition,
    footer,
)
from services.ingredient_lookup import clean_dish_name, get_ai_dish_estimate_with_retry, \
    calculate_portion_from_ai_estimate, save_review_dish
from services.message_builder import calculate_profile_results
from states import DiaryForm

router = Router()

@router.message(F.text == "📖 Дневник")
async def diary_menu_handler(
    message: Message,
) -> None:
    await diary_follow_handler(message)

@router.message(F.text == "⬅️ Назад")
async def back_to_main_menu_handler(
    message: Message,
) -> None:

    await message.answer(
        "Главное меню:",
        reply_markup=main_menu_keyboard,
    )

@router.message(F.text == "⬅️ К дневнику")
async def back_to_diary_menu_handler(
    message: Message,
) -> None:

    await message.answer(
        "Меню сегодня:",
        reply_markup=diary_menu_keyboard,
    )

async def diary_follow_handler(message: Message,) -> None:

    await message.answer(
        "Раздел дневника питания:",
        reply_markup=diary_menu_keyboard,
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
    results = calculate_profile_results(profile)
    total_energy = results["total_energy"]
    foods = get_today_food_logs(telegram_id)
    if len(foods) == 0:
        summary = (
                "Ваш журнал пока пуст.\n"
                + "-" * 10 +
                f"\n🎯 Текущая цель: {TARGETS[profile.target]['title']}\n"
                f"🍽 Калорийность: <b>{total_energy}</b> ккал,\n"
                f"Съедено: <b>0</b> ккал,\n"
                f"Осталось: <b>{total_energy}</b> ккал,\n"
        )
        await message.answer(
            summary,
            reply_markup=change_diary_keyboard,
        )
        return
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
        print("AI FALLBACK:", data["name"], "->", not_found)

        dish_name = clean_dish_name(data["name"])

        estimate = get_ai_dish_estimate_with_retry(
            dish=dish_name,
            max_attempts=3,
        )

        if not estimate:
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
        footer(total, "recipe"),
        reply_markup=diary_menu_keyboard,
    )

    await state.clear()

@router.message(F.text == "🗑 Удалить")
async def del_dish_diary_handler(
    message: Message,
    state: FSMContext,
) -> None:
    await state.set_state(DiaryForm.waiting_delete_number)
    await message.answer("Введите номер блюда, которое удаляем.")

@router.message(DiaryForm.waiting_delete_number)
async def dish_handler_delete(
    message: Message,
    state: FSMContext,
) -> None:
    text = message.text.strip()

    if not text.isdigit():
        await message.answer("Введите номер блюда числом.")
        return

    dish_number = int(text)

    if dish_number <= 0:
        await message.answer("Введите номер блюда больше нуля.")
        return

    data = await state.get_data()
    log_map = data.get("log_map", {})
    log_id = log_map.get(str(dish_number))

    if log_id is None:
        await message.answer("Записи с таким номером нет.")
        return

    delete_food_log(log_id)

    await message.answer("🗑 Запись удалена.",
                         reply_markup=diary_menu_keyboard,)
    await state.clear()

@router.message(F.text == "✏️ Изменить")
async def update_dish_diary_handler(
    message: Message,
    state: FSMContext,
) -> None:
    await state.set_state(DiaryForm.waiting_edit_number)
    await message.answer("Введите номер блюда, которое нужно изменить.")


@router.message(DiaryForm.waiting_edit_number)
async def dish_handler_update(
    message: Message,
    state: FSMContext,
) -> None:
    data = await state.get_data()

    if not data.get("log_map"):
        await message.answer("Сначала откройте дневник за сегодня.")
        return

    text = message.text.strip()

    if not text.isdigit():
        await message.answer("Введите номер блюда числом.")
        return

    dish_number = int(text)

    if dish_number <= 0:
        await message.answer("Введите номер блюда больше нуля.")
        return

    log_map = data.get("log_map", {})
    log_id = log_map.get(str(dish_number))

    if log_id is None:
        await message.answer("Записи с таким номером нет.")
        return

    food_old = get_food_log_by_id(log_id)

    if food_old is None:
        await message.answer("Запись не найдена.")
        await state.clear()
        return

    await state.update_data(log_id=log_id, food_old=food_old)

    await state.set_state(DiaryForm.waiting_edit_name)
    await message.answer(
        f"Текущее блюдо:\n"
        f"🍽 {food_old.food_name}\n"
        f"⚖️ {food_old.weight} г\n\n"
        f"Введите новое название блюда."
    )


@router.message(DiaryForm.waiting_edit_name)
async def dish_edit_name_handler(
    message: Message,
    state: FSMContext,
) -> None:
    text = message.text.strip()

    if not text:
        await message.answer("Введите новое название блюда.")
        return

    await state.update_data(name=text)
    await state.set_state(DiaryForm.waiting_edit_weight)
    await message.answer("Введите новый вес блюда в граммах.")


@router.message(DiaryForm.waiting_edit_weight)
async def dish_edit_weight_handler(
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

    old_name = data["food_old"].food_name
    total, not_found = calculate_nutrition(
        [
            {
                "name": data["name"],
                "weight": data["weight"],
            }
        ]
    )

    if data['name'] == old_name:
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

        log_id = data.get("log_id")

        if not log_id:
            await message.answer("Не удалось определить запись для изменения.")
            await state.clear()
            return

        update_food_log(log_id, food_log_data)

        await message.answer(
            f"✅ Запись обновлена:\n\n"
            f"🍽 {food_log_data['food_name']}\n"
            f"⚖️ Вес: {food_log_data['weight']} г"
        )

        await message.answer(
            footer(total, "recipe"),
            reply_markup=diary_menu_keyboard,
        )

        await state.clear()
        return

    if not_found:
        print("AI FALLBACK:", data["name"], "->", not_found)

        dish_name = clean_dish_name(data["name"])

        estimate = get_ai_dish_estimate_with_retry(
            dish=dish_name,
            max_attempts=3,
        )

        if not estimate:
            save_or_increment_cache(cache_path, not_found)

            await message.answer(
                "⚠️ Блюдо пока отсутствует в базе ингредиентов.\n"
                "Оно добавлено в очередь на обработку."
            )
            await state.clear()
            return

    portion = calculate_portion_from_ai_estimate(estimate, weight)
    print(portion)
    profile = get_user_profile(message.from_user.id)

    if profile is None:
        await message.answer("Профиль пользователя не найден.")
        await state.clear()
        return

    # food_log_data = {
    #     "user_id": profile.id,
    #     "food_name": data["name"],
    #     "weight": data["weight"],
    #     "kcal": total["kcal"],
    #     "protein": total["protein"],
    #     "fat": total["fat"],
    #     "carbs": total["carbs"],
    #     "source": "manual",
    # }
    food_log_data = {
        "user_id": profile.id,
        "food_name": portion["name_ru"],
        "weight": portion["weight_g"],
        "kcal": portion["kcal"],
        "protein": portion["protein"],
        "fat": portion["fat"],
        "carbs": portion["carbs"],
        "source": "ai_estimate",
    }
    log_id = data.get("log_id")

    if not log_id:
        await message.answer("Не удалось определить запись для изменения.")
        await state.clear()
        return

    update_food_log(log_id, food_log_data)

    dish_per_100g = {
        "name_ru": estimate.name_ru,
        "kcal_per_100g": estimate.nutrition_per_100g.kcal,
        "protein_per_100g": estimate.nutrition_per_100g.protein,
        "fat_per_100g": estimate.nutrition_per_100g.fat,
        "carbs_per_100g": estimate.nutrition_per_100g.carbs,
        "source": "ai_estimate",
        "needs_review": True,
        "status": "pending",
    }

    save_review_dish(dish_per_100g)

    total_for_footer = {
        "weight": portion["weight_g"],
        "kcal": portion["kcal"],
        "protein": portion["protein"],
        "fat": portion["fat"],
        "carbs": portion["carbs"],
        "kcal_100g": estimate.nutrition_per_100g.kcal,
        "protein_100g": estimate.nutrition_per_100g.protein,
        "fat_100g": estimate.nutrition_per_100g.fat,
        "carbs_100g": estimate.nutrition_per_100g.carbs,
    }

    await message.answer(
        f"✅ Запись обновлена:\n\n"
        f"🍽 {food_log_data['food_name']}\n"
        f"⚖️ Вес: {food_log_data['weight']} г"
    )

    await message.answer(
        f"⚠️ КБЖУ рассчитано ИИ приблизительно.\n\n"
        + footer(total_for_footer, "recipe"),
        reply_markup=diary_menu_keyboard,
    )

    await state.clear()

@router.message(F.text == "🔥 Остаток")
async def remainder_kcal_handler(
    message: Message
) -> None:
    telegram_id = message.from_user.id
    profile = get_user_profile(message.from_user.id)
    target_title = TARGETS.get(profile.target)["title"]
    if profile is None:
        await message.answer("Профиль пользователя не найден.")
        return
    foods = get_today_food_logs(telegram_id)
    await  message.answer(f"🎯 Ваша цель {target_title}")
    if len(foods) == 0:
        results = calculate_profile_results(profile)
        total_energy = results["total_energy"]
        await message.answer(f"🔥 Осталось: {total_energy} ккал.")
        await message.answer("Вы не потребляли еще калории сегодня.")
    else:
        results = calculate_profile_results(profile)
        total_energy = results["total_energy"]
        total_protein = results["bju"]['protein']
        total_fat = results["bju"]["fat"]
        total_carbs = results["bju"]["carbs"]
        eaten_kcal = sum(food.kcal for food in foods)
        eaten_protеin = sum(food.protein for food in foods)
        eaten_fat = sum(food.fat for food in foods)
        eaten_carbs = sum(food.carbs for food in foods)

        remainder_kcal = round(total_energy - eaten_kcal)
        if remainder_kcal > 0:
            answer = ""
            answer += (f"🔥 Калории: {eaten_kcal} / {total_energy} ккал.\n"
                       f"Осталось: {remainder_kcal} ккал.\n")
            answer += (f"🥩 Белки: {eaten_protеin} / {total_protein} г.\n"
                       f"Осталось: {round(total_protein - eaten_protеin)} г\n")
            answer += (f"\t🧈 Жиры: {eaten_fat} / {total_fat} г. \n"
                       f"Осталось: {round(total_fat - eaten_fat)} г\n")
            answer += (f"\t🍞 Углеводы: {eaten_carbs} / {total_carbs} г.\n"
                       f"Осталось: {round(total_carbs - eaten_carbs)} г")
            await message.answer(answer)
        elif remainder_kcal == 0:
            await message.answer(
                "🙏 Вы идеально уложились в дневную норму калорий."
            )
        else:
            await message.answer(
                f"⚠️ Лимит превышен на: {abs(remainder_kcal)} ккал."
            )
    await message.answer("📖 Дневник питания:",
                         reply_markup=diary_menu_keyboard)

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
    await message.answer(answer, reply_markup=diary_menu_keyboard)

@router.message(F.text == "📊 Статистика")
async def history_day_handler(message: Message, statistic_menu_keyboard=None) -> None:
    await message.answer("📊 Статистика питания",
                         reply_markup=statistics_menu_keyboard)

async def build_statistics_text(
    message: Message,
    period_days: int,
) -> None:

    profile = get_user_profile(message.from_user.id)

    if profile is None:
        await message.answer("Профиль не найден.")
        return

    target_title = TARGETS.get(profile.target)["title"]
    results = calculate_profile_results(profile)
    total_energy = results["total_energy"]

    stats = get_food_stats_by_days(
        user_id=profile.id,
        days=period_days,
    )

    answer = f"📊 Статистика питания за {period_days} дней\n\n"
    answer += f"🔥 Калорий съедено: {stats['summary']['kcal']} ккал\n"
    answer += f"📅 Среднее в день: {stats['average']['kcal']} ккал\n"
    answer += f"🥩 Белки: {stats['summary']['protein']} г\n"
    answer += f"🧈 Жиры: {stats['summary']['fat']} г\n"
    answer += f"🍞 Углеводы: {stats['summary']['carbs']} г\n\n"
    answer += f"🎯 Цель: {target_title}\n"
    answer += f"🍽 Норма: {total_energy} ккал/день\n\n"
    answer += f"✅ Дней с записями в дневнике: {stats['tracked_days']} из {period_days}"

    await message.answer(answer)

    remainder_kcal = round(total_energy - stats["average"]["kcal"])

    if remainder_kcal > 0:
        result_text = (
            f"🔥 Среднее за день: {stats['average']['kcal']} / "
            f"{total_energy} ккал.\n"
            f"✅ В среднем ниже нормы на {remainder_kcal} ккал."
        )
    elif remainder_kcal == 0:
        result_text = "🙏 Средняя калорийность идеально совпала с дневной нормой."
    else:
        result_text = (
            f"🔥 Среднее за день: {stats['average']['kcal']} / "
            f"{total_energy} ккал.\n"
            f"⚠️ В среднем выше нормы на {abs(remainder_kcal)} ккал."
        )

    await message.answer(
        result_text,
        reply_markup=statistics_menu_keyboard,
    )

@router.message(F.text == "📊 За 7 дней")
async def statistic_week_handler(
    message: Message,
) -> None:
    await build_statistics_text(message, 7)

@router.message(F.text == "📈 За 30 дней")
async def statistic_month_handler(
        message: Message,
) -> None:
    await build_statistics_text(message, 30)

@router.message(F.text == "⬅️ К дневнику")
async def back_to_statistic_menu_handler(
    message: Message,
) -> None:

    await message.answer("Меню дневника.",
                         reply_markup=diary_menu_keyboard)