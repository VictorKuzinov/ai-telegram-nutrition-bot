from pathlib import Path

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from ai.gigachat import (
    get_access_token,
    call_gigachat_vision,
    call_gigachat,
)
from db.repositories import (
    create_food_log,
    get_user_profile,
)
from keyboards import (
    ai_menu_keyboard,
    confirm_food_keyboard,
    main_menu_keyboard,
    confirm_save_keyboard,
)
from nutrition.nutrition_calc import (
    calculate_nutrition,
    footer,
    calc_bmr,
    calc_base_calories,
    calc_energy_total,
)
from nutrition.nutrition_cache import (
    cache_path,
    save_or_increment_cache,
)
from services.message_ai_parser import (
    clean_recipe_output,
    parse_ingredients_recipe,
    parse_ingredients_menu
)
from states import PhotoForm, RecipeForm, MenuForm

router = Router()

UPLOAD_DIR = Path("picture/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.message(F.text == "🤖 AI функции")
async def ai_menu_handler(
    message: Message,
) -> None:
    await message.answer(
        f"Выберите действие:",
        reply_markup=ai_menu_keyboard,
    )

@router.message(Command('photo'))
async def photo_handler(
    message: Message,
    state: FSMContext,
) -> None:
    await photo_from_menu_handler(message, state)


@router.message(F.text == "📷 Распознать блюдо")
async def photo_from_menu_handler(
    message: Message,
    state: FSMContext,
) -> None:
    await state.set_state(PhotoForm.waiting_photo)
    await message.answer(
        "Отправьте фото блюда. \n"
        "Можно сделать снимок камерой или выбрать "
        "изображение из галереи"
    )

@router.message(PhotoForm.waiting_photo, F.photo)
async def process_food_photo_handler(
    message: Message,
    state: FSMContext,
) -> None:

    photo = message.photo[-1]

    image_path = (
            UPLOAD_DIR /
            f"{photo.file_id}.jpg"
    )

    await message.bot.download(
        photo,
        destination=image_path,
    )
    print(image_path.exists())
    await message.answer("Фото получил, начинаю распознавание...")

    access_token = get_access_token()

    content = call_gigachat_vision(
        str(image_path),
        access_token,
    )

    if not content:
        await message.answer(
            "⚠️ Не удалось распознать блюдо. Попробуйте другое фото."
        )
        await state.clear()
        return
    await message.answer(f"Распознано блюдо: {content}")
    ingredients = parse_ingredients_recipe(content)

    if not ingredients:
        await message.answer(
            "Не удалось разобрать ингредиенты. Попробуйте другое фото или введите блюдо вручную."
        )
        await state.set_state(PhotoForm.edit_ingredient_name)
        return

    await state.update_data(
        ai_ingredients=ingredients,
        ai_raw_result=content,
    )

    ingredients_text = "\n".join(
        f"• {ingredient['name']}"
        for ingredient in ingredients
    )
    await state.set_state(PhotoForm.confirm_ingredient)

    await message.answer(
        f"Я вижу:\n"
        f"{ingredients_text}\n\n"
        f"Всё верно?",
        reply_markup=confirm_food_keyboard,
    )

@router.callback_query(PhotoForm.confirm_ingredient)
async def confirm_food_handler(
        callback: CallbackQuery,
        state: FSMContext,
) -> None:
    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    if callback.data == "confirm_food_yes":
        await state.update_data(use_ai_ingredients=True)
        await state.set_state(PhotoForm.waiting_weight)
        await callback.message.answer(
            "✅ Принято. Использую распознанные ингредиенты.\n"
            "Введите общий вес порции в граммах:"
        )

    elif callback.data == "confirm_food_no":
        await state.update_data(use_ai_ingredients=False)
        await state.set_state(PhotoForm.edit_ingredient_name)
        await callback.message.answer(
            "Введите блюдо или ингредиенты вручную:"
        )

    elif callback.data == "confirm_food_cancel":
        await state.clear()
        await callback.message.answer(
            "Распознавание отменено."
        )

    else:
        await callback.message.answer(
            "Пожалуйста, выберите вариант кнопкой."
        )

    await callback.answer()

@router.message(PhotoForm.waiting_weight)
async def weight_handler(
    message: Message,
    state: FSMContext,
) -> None:

    text = message.text.strip()

    if not text.isdigit():
        await message.answer(
            "Введите вес числом в граммах."
        )
        return

    weight = int(text)

    if weight <= 0:
        await message.answer(
            "Вес должен быть больше нуля."
        )
        return

    data = await state.get_data()

    ingredients = data.get("ai_ingredients", [])
    corrected_food = data.get("corrected_food")
    use_ai_ingredients = data.get("use_ai_ingredients", False)

    if use_ai_ingredients and ingredients:
        ai_total_weight = sum(item["weight"] for item in ingredients)

        if ai_total_weight <= 0:
            await message.answer("Не удалось определить вес ингредиентов.")
            await state.clear()
            return

        ratio = weight / ai_total_weight

        parsed_ingredients = [
            {
                "name": item["name"],
                "weight": item["weight"] * ratio,
            }
            for item in ingredients
        ]

        food_title = ", ".join(item["name"] for item in ingredients)

    else:
        food_title = corrected_food

        parsed_ingredients = [
            {
                "name": food_title,
                "weight": weight,
            }
        ]

    if not food_title:
        await message.answer("Не удалось определить блюдо.")
        await state.clear()
        return

    total, not_found = calculate_nutrition(parsed_ingredients)
    if not_found:
        save_or_increment_cache(
            cache_path,
            not_found,
        )
        await message.answer(
            "⚠️ Блюдо пока отсутствует в базе ингредиентов.\n"
            "Оно добавлено в очередь на обработку."
        )
        await state.clear()
        return
    else:
        profile = get_user_profile(message.from_user.id)

        if profile is None:
            await message.answer("Профиль пользователя не найден.")
            await state.clear()
            return

        food_log_data = {
            "user_id": profile.id,
            "food_name": food_title,
            "weight": weight,
            "kcal": total["kcal"],
            "protein": total["protein"],
            "fat": total["fat"],
            "carbs": total["carbs"],
            "source": "photo",
        }
        await state.update_data(
            food_log_data=food_log_data,
            calculated_total=total,
        )
        await state.set_state(PhotoForm.confirm_save)

        await message.answer(
            f"🍽 {food_title}\n"
            f"⚖️ Вес: {weight} г\n"
            + footer(total, "recipe")
        )

        await message.answer(
            "Добавить это блюдо в дневник?",
            reply_markup=confirm_save_keyboard,
        )

@router.callback_query(PhotoForm.confirm_save)
async def confirm_save_handler(
        callback: CallbackQuery,
        state: FSMContext,
) -> None:
    data = await state.get_data()

    if callback.data == "save_food_yes":
        food_log_data = data.get("food_log_data")

        if food_log_data:
            create_food_log(food_log_data)
            await callback.message.answer(
                f"✅ Блюдо сохранено в Ваш дневник:\n\n"
                f"🍽 {food_log_data['food_name']}\n"
                f"⚖️ Вес: {food_log_data['weight']} г"
            )
            total = data.get("calculated_total")
            await callback.message.answer(
                 footer(total, "recipe")
            )

    elif callback.data == "save_food_no":
        await callback.message.answer("👌 Не сохраняю.")

    await state.clear()
    await callback.answer()

@router.callback_query(PhotoForm.confirm_save)
async def confirm_save_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    data = await state.get_data()

    if callback.data == "save_food_yes":
        food_log_data = data.get("food_log_data")
        total = data.get("calculated_total")

        if food_log_data:
            create_food_log(food_log_data)

            await callback.message.answer(
                f"✅ Блюдо сохранено в Ваш дневник:\n\n"
                f"🍽 {food_log_data['food_name']}\n"
                f"⚖️ Вес: {food_log_data['weight']} г"
            )

            if total:
                await callback.message.answer(
                    footer(total, "recipe")
                )

    elif callback.data == "save_food_no":
        await callback.message.answer("👌 Не сохраняю.")

    await state.clear()
    await callback.answer()

@router.message(PhotoForm.edit_ingredient_name)
async def edit_ingredient_name_handler(
    message: Message,
    state: FSMContext,
) -> None:

    text = message.text.strip()

    await state.update_data(
        corrected_food=text,
        use_ai_ingredients=False,
    )

    await state.set_state(
        PhotoForm.waiting_weight
    )

    await message.answer(
        "Введите вес порции в граммах:"
    )

@router.message(PhotoForm.waiting_photo)
async def wrong_photo_input_handler(
        message: Message,
) -> None:
    await message.answer(
        "Нужно отправить именно фото блюда."
    )

@router.message(F.text == "⬅️ Назад")
async def back_to_main_menu_handler(
    message: Message,
) -> None:

    await message.answer(
        "Главное меню:",
        reply_markup=main_menu_keyboard,
    )

@router.message(Command('recipe'))
async def recipe_handler(
        message: Message,
        state: FSMContext,
) -> None:
    await start_recipe_flow(message, state)

@router.message(F.text == "🍲 Создать рецепт")
async def recipe_from_menu_handler(
        message: Message,
        state: FSMContext,
) -> None:
    await message.answer("🍳 Получить рецепт:")
    await start_recipe_flow(message, state)

async def start_recipe_flow(
        message: Message,
        state: FSMContext,
) -> None:
    await state.set_state(RecipeForm.waiting_recipe)
    await message.answer("Что Вы хотите приготовить?")

@router.message(RecipeForm.waiting_recipe)
async def recipe_handler(
        message: Message,
        state: FSMContext,
) -> None:
    await state.update_data(recipe=message.text)
    await state.set_state(RecipeForm.waiting_persons)
    await message.answer("На сколько человек блюдо?")

@router.message(RecipeForm.waiting_persons)
async def person_handler(
        message: Message,
        state: FSMContext,
) -> None:
    await state.update_data(persons=message.text)
    await state.set_state(RecipeForm.waiting_kcal)
    await message.answer("Ограничение по калориям?")

@router.message(RecipeForm.waiting_kcal)
async def kcal_handler(
        message: Message,
        state: FSMContext,
) -> None:
    await state.update_data(kcal=message.text)
    await state.set_state(RecipeForm.waiting_wishes)
    await message.answer("Дополнительные пожелания?")

def generate_user_prompt_recipe(data:dict) -> str:
    user_prompt = f"""
        Ты нутрициолог и повар.
        
        Составь рецепт блюда.
        
        Основной запрос:
        {data["recipe"]}
        
        Количество человек:
        {data["persons"]}
        
        Ограничение по калориям:
        {data["kcal"]}

        Дополнительные пожелания:
        {data["wishes"]}
        
        Требования:
        - краткий формат;
        - список ингредиентов;
        - пошаговое приготовление;
        - примерная калорийность;
        - б`ез длинных вступлений.
    """
    return user_prompt


def generate_user_prompt_menu(data: dict, daily_kcal: float) -> str:
    user_prompt = f"""
        Ты нутрициолог и повар.

        Составь меню на день
        примерно на {daily_kcal}

        Количество приемов пищи:
        {data["meal_count"]}

        Дополнительные пожелания:
        {data["wishes"]}

        Требования:
        Если приёмов пищи больше трёх,
        дополнительные называй "Перекус".
    """
    return user_prompt


@router.message(RecipeForm.waiting_wishes)
async def wishes_handler(
        message: Message,
        state: FSMContext,
) -> None:
    await state.update_data(wishes=message.text)
    await message.answer("Формирую рецепт...")
    data = await state.get_data()

    access_token = get_access_token()
    user_prompt = generate_user_prompt_recipe(data)
    ai_text = call_gigachat(access_token, mode='recipe', user_prompt=user_prompt)

    result = clean_recipe_output(ai_text)
    parsed = parse_ingredients_recipe(result)

    if not parsed:
        await message.answer(result)
        await message.answer(
            "⚠️ Не удалось рассчитать КБЖУ: ингредиенты не распознаны."
        )
        await state.clear()
        return

    total, not_found = calculate_nutrition(parsed)

    answer = result.strip()
    answer += "\n" + footer(total, "recipe")

    if not_found:
        answer += "\n⚠ Не учтены в расчёте:\n"

        for item in not_found:
            answer += f"- {item}\n"

        save_or_increment_cache(cache_path, not_found)

    await message.answer(answer)
    await state.clear()

@router.message(Command('menu'))
async def menu_handler(
        message: Message,
        state: FSMContext,
) -> None:
    await start_menu_flow(message, state)

@router.message(F.text == "📋 Меню на день")
async def menu_from_menu_handler(
        message: Message,
        state: FSMContext,
) -> None:
    await message.answer("🍳 Получить меню на день:")
    await start_menu_flow(message, state)

async def start_menu_flow(
        message: Message,
        state: FSMContext,
) -> None:
    await state.set_state(MenuForm.waiting_meal_count)
    await message.answer("Введите на сколько приемов пищи создать меню (от 3 до 6)?")

@router.message(MenuForm.waiting_meal_count)
async def wishes_meal_count(
    message: Message,
    state: FSMContext,
) -> None:
    if not message.text.isdigit():
        await message.answer("Введите число от 3 до 6")
        return

    meal_count = int(message.text)

    if meal_count < 3 or meal_count > 6:
        await message.answer("Введите число от 3 до 6")
        return

    await state.update_data(meal_count=meal_count)
    await state.set_state(MenuForm.waiting_wishes)
    await message.answer("Введите пожелания к меню (или напишите 'нет')")

@router.message(MenuForm.waiting_wishes)
async def wishes_handler(
        message: Message,
        state: FSMContext,
) -> None:
    await state.update_data(wishes=message.text)
    await message.answer("Формирую меню...")
    answer = ""
    data = await state.get_data()
    profile = get_user_profile(message.from_user.id)
    if profile is None:
        await message.answer("Профиль пользователя не найден.")
        await state.clear()
        return
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
    access_token = get_access_token()
    user_prompt = generate_user_prompt_menu(data, total_energy)
    ai_text = call_gigachat(
        access_token,
        mode='menu',
        user_prompt=user_prompt
    )
    if not ai_text:
        await message.answer("⚠️ Не удалось получить меню от ИИ.")
        await state.clear()
        return
    answer += str(ai_text).strip()
    parsed_menu = parse_ingredients_menu(ai_text)
    if not parsed_menu:
        await message.answer(
            "⚠️ Не удалось рассчитать КБЖУ: ингредиенты не распознаны."
        )
        await state.clear()
        return
    meals: dict[str, list[dict]] = {}

    for item in parsed_menu:
        meal = item["meal"]

        if meal not in meals:
            meals[meal] = []

        meals[meal].append(item)

    for meal_name, ingredients in meals.items():
        total, not_found = calculate_nutrition(ingredients)

        answer += "\n" + "═" * 16 + "\n"
        answer += f"\nПриём пищи: {meal_name}\n"
        answer += footer(total, "menu")

        if not_found:
            answer += "\n⚠ Не учтены в расчёте:\n"
            for item in not_found:
                answer += f"- {item}\n"
            save_or_increment_cache(cache_path, not_found)

    await message.answer(answer)
    await state.clear()
