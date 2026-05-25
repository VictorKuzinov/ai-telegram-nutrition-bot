from pathlib import Path

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from ai.gigachat import get_access_token, call_gigachat_vision, call_gigachat_recipe
from db.repositories import create_food_log, get_user_profile
from keyboards import (
    ai_menu_keyboard,
    confirm_food_keyboard, main_menu_keyboard,
)
from nutrition.nutrition_calc import (
    calculate_nutrition,
    footer_recipe,
)
from nutrition.nutrition_cache import (
    cache_path,
    save_or_increment_cache,
)
from services.message_ai_parser import parse_ingredients, clean_recipe_output
from states import PhotoForm, RecipeForm

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
        access_token
    )

    await message.answer(f"Распознано блюдо: {content}")
    ingredients = parse_ingredients(content)

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
        f"• {ingredient[0]}"
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
        await state.set_state(PhotoForm.waiting_weight)
        await callback.message.answer(
            "Введите общий вес порции в граммах:"
        )

    elif callback.data == "confirm_food_no":
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

    if corrected_food:
        food_title = corrected_food
    else:
        food_title = ", ".join(
            ingredient["name"]
            for ingredient in ingredients
        )

    await state.update_data(
        total_weight=weight,
    )

    parsed_ingredients = [
        {
            "name": food_title,
            "weight": weight,
        }
    ]

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

        create_food_log(food_log_data)

        await message.answer(
            f"✅ Блюдо сохранено:\n\n"
            f"🍽 {food_title}\n"
            f"⚖️ Вес: {weight} г"
        )

        await message.answer(
            footer_recipe(total)
        )

    await state.clear()

@router.message(PhotoForm.edit_ingredient_name)
async def edit_ingredient_name_handler(
    message: Message,
    state: FSMContext,
) -> None:

    text = message.text.strip()

    await state.update_data(
        corrected_food=text,
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
    ai_text = call_gigachat_recipe(access_token, mode='recipe', user_prompt=user_prompt)

    result = clean_recipe_output(ai_text)
    parsed = parse_ingredients(result)

    if not parsed:
        await message.answer(result)
        await message.answer(
            "⚠️ Не удалось рассчитать КБЖУ: ингредиенты не распознаны."
        )
        await state.clear()
        return

    total, not_found = calculate_nutrition(parsed)

    answer = result.strip()
    answer += "\n" + footer_recipe(total)

    if not_found:
        answer += "\n⚠ Не учтены в расчёте:\n"

        for item in not_found:
            answer += f"- {item}\n"

        save_or_increment_cache(cache_path, not_found)

    await message.answer(answer)
    await state.clear()